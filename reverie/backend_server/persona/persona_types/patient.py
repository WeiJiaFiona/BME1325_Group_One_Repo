
import datetime
from datetime import timedelta
import random
import sys
import bisect
sys.path.append('../../')
import utils
from persona.persona import *
from downstream_units.disposition_target_resolver import DispositionTargetResolver
from persona.memory_structures.scratch_types.patient_scratch import patient_scratch
from runtime_evidence import ensure_queue_exposure, stamp_event
from week7_logic import boarding_timeout_reached, testing_kind_for_ctas


class Patient(Persona):
    EVENT_TRIAGE_FIRST_CONTACT = "TRIAGE_FIRST_CONTACT"
    EVENT_BEDSIDE_FIRST_CONTACT = "BEDSIDE_FIRST_CONTACT"
    EVENT_DOCTOR_FIRST_ASSESS = "DOCTOR_FIRST_ASSESS"
    EVENT_TEST_ORDERED = "TEST_ORDERED"
    EVENT_TEST_RESULT_READY = "TEST_RESULT_READY"
    EVENT_DISPOSITION_CHANGED = "DISPOSITION_CHANGED"
    EVENT_HANDOFF_OCCURRED = "HANDOFF_OCCURRED"
    state_to_act_pronunciatio = {
        "WAITING_FOR_TRIAGE": "\u231b",
        "TRIAGE": "\u2695\uFE0F",
        "WAITING_FOR_NURSE": "\u231b",
        "WAITING_FOR_FIRST_ASSESSMENT": "\uD83D\uDECC",
        "WAITING_FOR_TEST": "\u231b",
        "GOING_FOR_TEST": "\uD83D\uDEB6\u200D\u2642\uFE0F",
        "WAITING_FOR_RESULT": "\u231b",
        "WAITING_FOR_DOCTOR": "\u231b",
        "ADMITTED_BOARDING": "\U0001f3e5"
        }

    time_increment = 0 # In minutes
    priority_factor = 0
    testing_result_time = 0
    testing_time = 0  # In minutes, set from meta.json
    testing_probability_by_ctas = {"1": 1.0, "2": 0.8, "3": 0.5, "4": 0.3, "5": 0.0}
    walkout_probability = 0.0
    walkout_check_minutes = 20
    post_discharge_linger_probability = 0.0
    post_discharge_linger_minutes = 0
    simulate_hospital_admission = False
    admission_probability_by_ctas = {}
    admission_boarding_minutes_min = 60
    admission_boarding_minutes_max = 480
    lab_turnaround_minutes = 20
    imaging_turnaround_minutes = 45
    boarding_timeout_minutes = 240
    transfer_broker = None
    disposition_target_resolver = None
    walkout_states = {
        "WAITING_FOR_TRIAGE",
        "TRIAGE",
        "WAITING_FOR_NURSE",
        "WAITING_FOR_TEST",
        "WAITING_FOR_RESULT",
        "WAITING_FOR_DOCTOR",
        "WAITING_FOR_EXIT",
        "WAITING_FOR_FIRST_ASSESSMENT",
    }
    def __init__(self, name, folder_mem_saved=False, role=None, ICD = None, seed=0):
        super().__init__(name,folder_mem_saved,role, seed)
        
        # <scratch> is the persona's scratch (short term memory) space. 
        scratch_saved = f"{folder_mem_saved}/bootstrap_memory/scratch.json"
        self.scratch = patient_scratch(scratch_saved)
        self.role = role
        # Default settings
        if(self.scratch.state == None):
            self.scratch.state = "WAITING_FOR_TRIAGE"
        if(self.scratch.next_step == None):
            self.scratch.next_step = "ed map:emergency department:waiting room:waiting room chair"
        if(self.scratch.ICD == None):
            self.scratch.ICD = ICD

    def _conversation_step_token(self):
        curr_time = getattr(self.scratch, "curr_time", None)
        if not curr_time:
            return None
        return int(curr_time.timestamp() // 60)

    def _minutes_per_step(self) -> int:
        return int(getattr(self.scratch, "time_scale_minutes_per_step", 1) or 1)

    def _runtime_step(self) -> int:
        return int(getattr(self, "runtime_step", 0) or 0)

    def _minute_for_step(self, step: int) -> int:
        return int(step) * self._minutes_per_step()

    def _stamp_event(self, event_name: str, curr_step: int) -> None:
        stamp_event(self.scratch.__dict__, event_name, curr_step, self._minutes_per_step())

    def stamp_ed_arrival(self, curr_step: int) -> None:
        if self.scratch.ed_arrival_minute is None:
            self._stamp_event("ed_arrival", curr_step)

    def stamp_triage_completed(self, curr_step: int) -> None:
        if self.scratch.triage_completed_minute is None:
            self._stamp_event("triage_completed", curr_step)

    def stamp_first_doctor_contact(self, curr_step: int) -> None:
        if self.scratch.first_doctor_contact_minute is None:
            self._stamp_event("first_doctor_contact", curr_step)

    def stamp_ed_exit(self, curr_step: int, disposition_status: str) -> None:
        if self.scratch.ed_exit_minute is None:
            self._stamp_event("ed_exit", curr_step)
        if self.scratch.care_completed_minute is None:
            self._stamp_event("care_completed", curr_step)
        self.scratch.disposition_status = disposition_status

    def ensure_queue_exposure_payload(self):
        self.scratch.queue_exposure = ensure_queue_exposure(self.scratch.__dict__)
        return self.scratch.queue_exposure

    def queue_conversation_event(self, event_name):
        if not event_name:
            return
        pending = getattr(self.scratch, "pending_conversation_events", None)
        if pending is None:
            self.scratch.pending_conversation_events = []
            pending = self.scratch.pending_conversation_events
        if event_name not in pending:
            pending.append(event_name)

    def mark_handoff(self):
        token = self._conversation_step_token()
        if token is not None:
            self.scratch.last_handoff_step = token
        self.queue_conversation_event(self.EVENT_HANDOFF_OCCURRED)

    def select_conversation_event(self, candidate_events):
        pending = list(getattr(self.scratch, "pending_conversation_events", []) or [])
        if not pending:
            return None
        token = self._conversation_step_token()
        cooldown = int(getattr(self.scratch, "conversation_cooldown_steps", 2) or 0)
        last_event = getattr(self.scratch, "last_conversation_event", None)
        last_step = getattr(self.scratch, "last_conversation_step", None)
        for event_name in candidate_events:
            if event_name not in pending:
                continue
            if (
                event_name == last_event
                and token is not None
                and last_step is not None
                and (token - int(last_step)) < cooldown
            ):
                continue
            self.scratch.active_conversation_event = event_name
            return event_name
        return None

    def consume_active_conversation_event(self):
        event_name = getattr(self.scratch, "active_conversation_event", None)
        if not event_name:
            return None
        pending = getattr(self.scratch, "pending_conversation_events", []) or []
        if event_name in pending:
            pending.remove(event_name)
        token = self._conversation_step_token()
        if token is not None:
            self.scratch.last_conversation_step = token
        self.scratch.last_conversation_event = event_name
        if event_name == self.EVENT_TEST_RESULT_READY and getattr(self.scratch, "curr_time", None):
            self.scratch.last_result_notified_at = self.scratch.curr_time
        self.scratch.active_conversation_event = None
        return event_name



    def _target_bed(self, maze, zone):
        if not zone:
            return None
        bed = maze.assign_bed(self.name, zone, self.scratch.bed_assignment)
        if bed:
            self.scratch.bed_assignment = list(bed)
            return maze.get_bed_address(zone, bed)
        return None

    def _release_bed(self, maze):
        """
        Free up the patient's bed assignment so capacity is not blocked.
        Safe to call multiple times.
        
        """

        maze.discharge_patient(self.name, self.scratch.injuries_zone)
        self.scratch.bed_assignment = None

    def _release_testing_resources(self, maze):
        lab_patients = getattr(maze, "lab_patients", [])
        if self.name in lab_patients:
            lab_patients.remove(self.name)

        imaging_patients = getattr(maze, "imaging_patients", [])
        if self.name in imaging_patients:
            imaging_patients.remove(self.name)

        diag_patients = maze.injuries_zones.get("diagnostic room", {}).get("current_patients", [])
        if self.name in diag_patients:
            diag_patients.remove(self.name)

    def _downstream_target(self) -> str:
        resolver = getattr(self.__class__, "disposition_target_resolver", None) or DispositionTargetResolver()
        return resolver.resolve(ctas_level=self.scratch.CTAS, admitted=True, rng=random)

    def _transfer_reason(self, target: str) -> str:
        return "critical_care_needed" if str(target).upper() == "ICU" else "inpatient_admission_needed"

    def _transfer_summary(self, target: str) -> str:
        return f"ED disposition to {str(target).upper()} for CTAS {self.scratch.CTAS or 'unknown'} patient"

    def _legacy_random_boarding(self):
        self.scratch.admitted_to_hospital = True
        self.scratch.admission_boarding_start = self.scratch.curr_time
        self.scratch.boarding_timeout_recorded = False
        self.scratch.boarding_timeout_at = None
        self.scratch.boarding_timeout_step = None
        self.scratch.boarding_timeout_minute = None
        boarding_minutes = random.uniform(
            self.admission_boarding_minutes_min,
            self.admission_boarding_minutes_max,
        )
        self.scratch.admission_boarding_end = (
            self.scratch.curr_time + timedelta(minutes=boarding_minutes)
        )
        self.scratch.state = "ADMITTED_BOARDING"
        self.scratch.disposition_status = "admit"
        self.scratch.next_step = (
            f"ed map:emergency department:{self.scratch.injuries_zone}:bed"
        )
        self.queue_conversation_event(self.EVENT_DISPOSITION_CHANGED)
        return True

    def _request_downstream_transfer(self, target: str):
        broker = getattr(self.__class__, "transfer_broker", None)
        if broker is None:
            return None
        current_step = self._runtime_step()
        response = broker.request_transfer(
            encounter_id=self.scratch.user_encounter_id or self.name,
            patient_id=self.scratch.user_patient_id or self.name,
            from_group="ED",
            to_group=str(target).upper(),
            from_unit="ED",
            to_unit=str(target).upper(),
            request_step=current_step,
            request_minute=self._minute_for_step(current_step),
            ctas_level=self.scratch.CTAS,
            reason=self._transfer_reason(target),
            summary=self._transfer_summary(target),
            requested_resources=["bed"],
            transfer_id=self.scratch.transfer_request_id,
        )
        self.scratch.transfer_request_id = response.transfer_id
        self.scratch.transfer_status = response.status
        self.scratch.transfer_next_check_step = response.next_check_step
        self.scratch.transfer_next_check_minute = response.next_check_minute
        self.scratch.transfer_completed_step = response.transfer_completed_step
        self.scratch.transfer_completed_minute = response.transfer_completed_minute
        self.scratch.assigned_downstream_bed = response.assigned_bed
        return response

    def _apply_pending_transfer(self, response) -> None:
        current_step = self._runtime_step()
        self.scratch.admitted_to_hospital = True
        self.scratch.transfer_status = "pending"
        self.scratch.boarding_timeout_recorded = False
        self.scratch.boarding_timeout_at = None
        self.scratch.boarding_timeout_step = None
        self.scratch.boarding_timeout_minute = None
        if self.scratch.admission_boarding_start is None:
            self.scratch.admission_boarding_start = self.scratch.curr_time
        if self.scratch.boarding_started_minute is None:
            self.scratch.boarding_started_step = current_step
            self.scratch.boarding_started_minute = self._minute_for_step(current_step)
        self.scratch.admission_boarding_end = None
        self.scratch.state = "ADMITTED_BOARDING"
        self.scratch.disposition_status = "admit"
        self.scratch.next_step = (
            f"ed map:emergency department:{self.scratch.injuries_zone}:bed"
        )
        self.queue_conversation_event(self.EVENT_DISPOSITION_CHANGED)

    def _apply_accepted_transfer(self, response, target: str) -> None:
        self.scratch.admitted_to_hospital = True
        self.scratch.transfer_status = "accepted"
        if self.scratch.admission_boarding_start is None:
            self.scratch.admission_boarding_start = self.scratch.curr_time
        self.scratch.admission_boarding_end = (
            self.scratch.curr_time + timedelta(minutes=int(response.expected_eta_minutes or 0))
        )
        self.scratch.state = "ADMITTED_BOARDING"
        self.scratch.disposition_status = "admit"
        self.scratch.next_step = (
            f"ed map:emergency department:{self.scratch.injuries_zone}:bed"
        )
        if str(target).upper() == "ICU":
            self.scratch.icu_admit_step = response.transfer_completed_step
            self.scratch.icu_admit_minute = response.transfer_completed_minute
            self.scratch.ward_transfer_step = None
            self.scratch.ward_transfer_minute = None
        else:
            self.scratch.ward_transfer_step = response.transfer_completed_step
            self.scratch.ward_transfer_minute = response.transfer_completed_minute
            self.scratch.icu_admit_step = None
            self.scratch.icu_admit_minute = None
        self.queue_conversation_event(self.EVENT_DISPOSITION_CHANGED)
        self.mark_handoff()

    def _maybe_retry_pending_transfer(self):
        if self.scratch.state != "ADMITTED_BOARDING":
            return
        if str(getattr(self.scratch, "transfer_status", "") or "").lower() != "pending":
            return
        next_check_minute = getattr(self.scratch, "transfer_next_check_minute", None)
        if next_check_minute is None:
            return
        current_minute = self._minute_for_step(self._runtime_step())
        if current_minute < int(next_check_minute):
            return
        if not self.scratch.disposition_target:
            return
        response = self._request_downstream_transfer(self.scratch.disposition_target)
        if response is None:
            return
        if response.status == "accepted":
            self._apply_accepted_transfer(response, self.scratch.disposition_target)
        else:
            self._apply_pending_transfer(response)


    def move(self, maze, personas, curr_tile, curr_time, data_collection):
        # Area
        if( maze.tiles[curr_tile[1]][curr_tile[0]]['arena'] not in data_collection["time_spent_area"].keys()):
            data_collection["time_spent_area"][maze.tiles[curr_tile[1]][curr_tile[0]]['arena']] = self.time_increment
        else:
            data_collection["time_spent_area"][maze.tiles[curr_tile[1]][curr_tile[0]]['arena']] += self.time_increment

        # State
        if ( self.scratch.state not in data_collection["time_spent_state"].keys()):
            data_collection["time_spent_state"][self.scratch.state] = self.time_increment
        else:
            data_collection["time_spent_state"][self.scratch.state] += self.time_increment

        # Free up the bed once the patient has started leaving so capacity is not blocked.
        if self.scratch.state == "LEAVING":
            self._release_bed(maze)

        data_collection.setdefault("left_department_by_choice", {"occurred": False})
        data_collection.setdefault("lingered_after_discharge", {"occurred": False})
        data_collection.setdefault("admitted_to_hospital", {"occurred": False})
        data_collection.setdefault("boarding_timeout_event", {"occurred": False})
        data_collection.setdefault("testing_kind", self.scratch.testing_kind)

        self.scratch.curr_tile = curr_tile
        self.scratch.curr_time = curr_time
        self._maybe_retry_pending_transfer()

        if (
            self.scratch.state == "ADMITTED_BOARDING"
            and not self.scratch.boarding_timeout_recorded
            and str(getattr(self.scratch, "transfer_status", "") or "").lower() != "accepted"
            and boarding_timeout_reached(
                self.scratch.admission_boarding_start,
                curr_time,
                self.boarding_timeout_minutes,
            )
        ):
            self.scratch.boarding_timeout_recorded = True
            self.scratch.boarding_timeout_at = curr_time
            self.scratch.boarding_timeout_step = self._runtime_step()
            self.scratch.boarding_timeout_minute = self._minute_for_step(self.scratch.boarding_timeout_step)
            data_collection["boarding_timeout_event"] = {
                "occurred": True,
                "timestamp": curr_time.strftime("%B %d, %Y, %H:%M:%S"),
                "threshold_minutes": float(self.boarding_timeout_minutes),
            }
            utils.log_runtime_event(
                "boarding timeout event recorded",
                sim_code=utils.static_sim_code,
                extra={
                    "patient": self.name,
                    "timestamp": curr_time.strftime("%B %d, %Y, %H:%M:%S"),
                    "threshold_minutes": float(self.boarding_timeout_minutes),
                },
            )
            memory_hook_manager = getattr(self, "auto_memory_hook_manager", None)
            if memory_hook_manager is not None:
                memory_hook_manager.record_boarding_timeout(
                    self,
                    step=int(getattr(self, "runtime_step", 0) or 0),
                    sim_time=curr_time,
                )

        # Generate if Patient should leave the ED right now
        if (
            self.walkout_probability > 0
            and not self.scratch.left_without_being_seen
            and self.scratch.state in self.walkout_states
            and not self.scratch.chatting_with
            and not self.scratch.time_to_next
        ):
            waited_minutes = data_collection["time_spent_state"][self.scratch.state]
            last_check = getattr(self.scratch, "walkout_last_check_minute", 0.0) or 0.0
            if waited_minutes - last_check >= self.walkout_check_minutes:
                self.scratch.walkout_last_check_minute = waited_minutes
                if random.random() <= self.walkout_probability:
                    self._initiate_walkout(maze, data_collection, waited_minutes, curr_time, personas)

        if self.scratch.lingering_after_discharge and not self.scratch.linger_recorded:
            data_collection["lingered_after_discharge"] = {
                "occurred": True,
                "decided_at": (self.scratch.linger_started_at.strftime("%B %d, %Y, %H:%M:%S")
                               if self.scratch.linger_started_at else None),
                "expected_duration_minutes": self.scratch.linger_duration_minutes,
            }
            self.scratch.linger_recorded = True

        if (
            self.scratch.lingering_after_discharge
            and self.scratch.linger_end_time
            and curr_time
            and curr_time >= self.scratch.linger_end_time
            and self.scratch.state == "DISCHARGED_WAITING"
        ):
            self._release_bed(maze)
            self.scratch.lingering_after_discharge = False
            self.scratch.state = "LEAVING"
            self.scratch.next_step = "ed map:emergency department:exit"
            self.scratch.act_path_set = False
            entry = data_collection.get("lingered_after_discharge")
            if isinstance(entry, dict) and entry.get("occurred"):
                entry["ended_at"] = curr_time.strftime("%B %d, %Y, %H:%M:%S")


        # plan = super().move(maze, personas, curr_tile, curr_time, data_collection)
        print("curr_tile",curr_tile)

        #Check for available doctor and assign if there isn't one already assigned and patient isn't waiting for triage or waiting for nurse
        # if(not self.scratch.assigned_doctor and self.scratch.state not in ["WAITING_FOR_TRIAGE", "TRIAGE", "WAITING_FOR_NURSE", "LEAVING"] 
        #    and maze.doctors_taking_more_patients != []):
        #     self.scratch.assigned_doctor = random.choice(maze.doctors_taking_more_patients)
        #     personas[self.scratch.assigned_doctor].assign_patient(maze.doctors_taking_more_patients, self)
        #     maze.patients_waiting_for_doctor.remove(self.name)

        # Check if the Patient chatting time is over
        if(self.scratch.chatting_end_time):
            if (self.scratch.chatting_end_time <= curr_time):
                # Reset variables back to default
                self.scratch.chatting_with = None
                self.scratch.chat  = None
                self.scratch.chatting_end_time  = None
                self.scratch.act_path_set = False

        # Special condition for patient to do whatever the medical staff tells them. next_step changed in plan.py.
        # To easily control what a patient should do next in a given room

        # If Patient isn't talking with other agent, control their movement
        if(self.scratch.chatting_with == None):
            if getattr(self.scratch, "user_controlled", False):
                plan = str(self.scratch.next_step or "ed map:emergency department:waiting room:waiting room chair")
                return self.execute(maze, personas, plan)

            assigned_doctor = personas.get(str(self.scratch.assigned_doctor), None)

            # If assigned_doctor name is set but the doctor object is gone, clear
            # the stale reference so the patient can be re-assigned.
            if self.scratch.assigned_doctor is not None and assigned_doctor is None:
                print(f"(Patient) {self.name}: clearing stale assigned_doctor "
                      f"'{self.scratch.assigned_doctor}' (not found in personas)")
                self.scratch.assigned_doctor = None

            if(self.scratch.assigned_doctor == None):
                # If waiting for results with timer expired but no doctor, transition
                # to WAITING_FOR_DOCTOR so rescue mechanism can re-assign one.
                if (self.scratch.state == "WAITING_FOR_RESULT"
                    and self.scratch.time_to_next
                    and self.scratch.curr_time >= self.scratch.time_to_next):
                    self.queue_conversation_event(self.EVENT_TEST_RESULT_READY)
                    self.scratch.state = "WAITING_FOR_DOCTOR"
                    priority = self.scratch.CTAS * (self.priority_factor / 2) if self.scratch.CTAS else 3
                    already_queued = any(entry[1] == self.name for entry in maze.patients_waiting_for_doctor)
                    if not already_queued:
                        bisect.insort_right(maze.patients_waiting_for_doctor,
                                            [priority, self.name])
                    print(f"(Patient) {self.name}: no doctor assigned, moved from "
                          f"WAITING_FOR_RESULT to WAITING_FOR_DOCTOR")

            # If they are waiting for test results check if results came back
            elif(
                self.scratch.state == "WAITING_FOR_RESULT"
                and self.scratch.time_to_next
                and self.scratch.curr_time >= self.scratch.time_to_next
                and assigned_doctor is not None
            ):
                if self.scratch.testing_kind == "lab":
                    self._release_testing_resources(maze)
                queue = assigned_doctor.scratch.assigned_patients_waitlist

                ready_for_disposition = True
                # If a staged disposition time is set, ensure we've reached it
                if self.scratch.disposition_ready_at and self.scratch.curr_time < self.scratch.disposition_ready_at:
                    ready_for_disposition = False
                already_in_queue = any(entry[1] == self.name for entry in queue)
                if ready_for_disposition and not already_in_queue:
                    bisect.insort_right(queue,
                                    [self.scratch.CTAS * (self.priority_factor / 2), self.name])
                    self.queue_conversation_event(self.EVENT_TEST_RESULT_READY)
                    self.scratch.state = "WAITING_FOR_DOCTOR"

            elif(self.scratch.state == "WAITING_FOR_FIRST_ASSESSMENT" and assigned_doctor is not None):
                queue = assigned_doctor.scratch.assigned_patients_waitlist

                bed_target = self._target_bed(maze, self.scratch.injuries_zone)
                ready_at = self.scratch.initial_assessment_ready_at
                if (not ready_at or self.scratch.curr_time >= ready_at):
                    current_arena = None
                    try:
                        current_arena = maze.tiles[curr_tile[1]][curr_tile[0]].get("arena")
                    except Exception:
                        current_arena = None
                    on_exact_bed_tile = (
                        bed_target
                        and bed_target[0] == curr_tile[0]
                        and bed_target[1] == curr_tile[1]
                    )
                    same_zone_with_bed_assignment = bool(
                        self.scratch.bed_assignment
                        and current_arena
                        and current_arena == self.scratch.injuries_zone
                    )
                    if ((not self.scratch.in_queue)
                        and (on_exact_bed_tile or same_zone_with_bed_assignment)):
                        self.scratch.in_queue = True
                        if not any(entry[1] == self.name for entry in queue):
                            bisect.insort_right(queue,
                                            [self.scratch.CTAS * self.priority_factor, self.name])

            elif (
                self.scratch.state == "WAITING_FOR_TEST"
                and (self.scratch.testing_kind or testing_kind_for_ctas(self.scratch.CTAS)) == "lab"
            ):
                self.scratch.testing_kind = "lab"
                data_collection["testing_kind"] = "lab"
                lab_patients = getattr(maze, "lab_patients", [])
                lab_capacity = max(1, int(getattr(maze, "lab_capacity", 1) or 1))
                if len(lab_patients) < lab_capacity and self.name not in lab_patients:
                    lab_patients.append(self.name)
                    self.scratch.testing_end_time = self.scratch.curr_time + timedelta(
                        minutes=float(self.lab_turnaround_minutes)
                    )
                    self.scratch.time_to_next = self.scratch.testing_end_time
                    self.scratch.state = "WAITING_FOR_RESULT"
                    bed_target = self._target_bed(maze, self.scratch.injuries_zone)
                    if bed_target:
                        self.scratch.next_step = f"<tile> {bed_target}"
                    self.scratch.next_room = self.scratch.injuries_zone
                    self.scratch.act_path_set = False
                    utils.log_runtime_event(
                        "lab slot occupied",
                        sim_code=utils.static_sim_code,
                        extra={
                            "patient": self.name,
                            "capacity": lab_capacity,
                            "in_progress": len(lab_patients),
                            "testing_end_time": self.scratch.testing_end_time.strftime("%B %d, %Y, %H:%M:%S"),
                        },
                    )

            # Patient self-manages testing: check if diagnostic room has space, go directly
            elif self.scratch.state == "WAITING_FOR_TEST":
                self.scratch.testing_kind = self.scratch.testing_kind or "imaging"
                data_collection["testing_kind"] = self.scratch.testing_kind
                diag_info = maze.injuries_zones.get("diagnostic room", {})
                current = diag_info.get("current_patients", [])
                imaging_patients = getattr(maze, "imaging_patients", [])
                capacity = max(1, int(getattr(maze, "imaging_capacity", diag_info.get("capacity", 5)) or 1))
                if len(current) < capacity and len(imaging_patients) < capacity and self.name not in current:
                    # Space available — go to diagnostic room
                    current.append(self.name)
                    if self.name not in imaging_patients:
                        imaging_patients.append(self.name)
                    self.scratch.next_step = "ed map:emergency department:diagnostic room:diagnostic table"
                    self.scratch.next_room = "diagnostic room"
                    self.scratch.state = "GOING_FOR_TEST"
                    self.scratch.testing_end_time = self.scratch.curr_time + timedelta(
                        minutes=float(self.imaging_turnaround_minutes)
                    )
                    self.scratch.act_path_set = False
                    # Remove from bedside_nurse_waiting if present
                    for entry in maze.injuries_zones.get("bedside_nurse_waiting", [])[:]:
                        if entry[1] == self.name:
                            maze.injuries_zones["bedside_nurse_waiting"].remove(entry)
                            break
                    utils.log_runtime_event(
                        "imaging slot occupied",
                        sim_code=utils.static_sim_code,
                        extra={
                            "patient": self.name,
                            "capacity": capacity,
                            "in_progress": len(imaging_patients),
                            "testing_end_time": self.scratch.testing_end_time.strftime("%B %d, %Y, %H:%M:%S"),
                        },
                    )

            # Patient self-manages diagnostic testing: when testing_end_time expires,
            # leave diagnostic room and walk back to bed.
            elif(self.scratch.state == "GOING_FOR_TEST"
                 and self.scratch.testing_end_time
                 and self.scratch.curr_time >= self.scratch.testing_end_time):
                self._release_testing_resources(maze)
                self.scratch.testing_end_time = None
                bed_target = self._target_bed(maze, self.scratch.injuries_zone)
                if bed_target:
                    self.scratch.next_step = f"<tile> {bed_target}"
                else:
                    self.scratch.next_step = f"ed map:emergency department:{self.scratch.injuries_zone}:bed"
                self.scratch.next_room = self.scratch.injuries_zone
                self.scratch.time_to_next = self.scratch.curr_time
                self.scratch.state = "WAITING_FOR_RESULT"
                self.scratch.act_path_set = False
                # Surge extra: push disposition gate forward so surge
                # slowdown is experienced in-bed after testing.
                surge_extra = float(self.scratch.stage2_surge_extra or 0)
                if surge_extra > 0:
                    self.scratch.disposition_ready_at = (
                        max(self.scratch.disposition_ready_at or self.scratch.curr_time,
                            self.scratch.curr_time)
                        + timedelta(minutes=surge_extra)
                    )
                utils.log_runtime_event(
                    "testing finished",
                    sim_code=utils.static_sim_code,
                    extra={
                        "patient": self.name,
                        "testing_kind": self.scratch.testing_kind,
                        "state": self.scratch.state,
                    },
                )

            # Safety: if GOING_FOR_TEST but no testing_end_time, auto-set it
            elif (self.scratch.state == "GOING_FOR_TEST" and not self.scratch.testing_end_time):
                turnaround = (
                    self.imaging_turnaround_minutes
                    if self.scratch.testing_kind == "imaging"
                    else self.lab_turnaround_minutes
                )
                self.scratch.testing_end_time = self.scratch.curr_time + timedelta(minutes=float(turnaround))
                utils.log_runtime_event(
                    "testing end time restored",
                    sim_code=utils.static_sim_code,
                    extra={
                        "patient": self.name,
                        "testing_kind": self.scratch.testing_kind,
                        "testing_end_time": self.scratch.testing_end_time.strftime("%B %d, %Y, %H:%M:%S"),
                    },
                )

            plan = str(self.scratch.next_step)

            # If the plan doesn't match the last assigned act_address
            # Means that the plan has changed and the Patient has to move now
            if(plan != self.scratch.act_address):
                # Patient now has to move to new position
                self.scratch.act_path_set = False
                self.scratch.act_address = plan.split("> ")[-1]

            # Patient leaves the ED
            if self.scratch.state == "WAITING_FOR_EXIT" and self.scratch.exit_ready_at and self.scratch.curr_time >= self.scratch.exit_ready_at:
                self.scratch.state = "LEAVING"
                self._release_bed(maze)
                self.scratch.next_step = "ed map:emergency department:exit"
                self.scratch.act_path_set = False

            # Admitted patient finishes boarding and leaves
            if self.scratch.state == "ADMITTED_BOARDING" and self.scratch.admission_boarding_end and self.scratch.curr_time >= self.scratch.admission_boarding_end:
                self.scratch.state = "LEAVING"
                self._release_bed(maze)
                self.scratch.next_step = "ed map:emergency department:exit"
                self.scratch.act_path_set = False

        else:
            # If they are chatting set the plan to talk with other persona
            plan = f"<persona> {self.scratch.chatting_with }"
            self.scratch.act_address = self.scratch.chatting_with 
            
        self.scratch.act_pronunciatio = self.state_to_act_pronunciatio.get(self.scratch.state, "\ud83e\udd22")

        return self.execute(maze, personas, plan)

    def _initiate_walkout(self, maze, data_collection, waited_minutes, curr_time, personas):
        """
        Trigger a patient walk-out event and remove the patient from any queues.
        """
        self.scratch.next_step = "ed map:emergency department:exit"
        self.scratch.act_path_set = False
        self.scratch.left_without_being_seen = True
        self.scratch.left_without_being_seen_time = curr_time
        self.scratch.left_without_being_seen_state = self.scratch.state
        self.scratch.left_without_being_seen_wait_minutes = waited_minutes
        self.scratch.walkout_recorded = True

        timestamp = curr_time.strftime("%B %d, %Y, %H:%M:%S") if curr_time else None
        data_collection["left_department_by_choice"] = {
            "occurred": True,
            "state": self.scratch.left_without_being_seen_state,
            "wait_minutes": waited_minutes,
            "timestamp": timestamp,
        }
        self._release_testing_resources(maze)

        if self.name in maze.triage_queue:
            maze.triage_queue.remove(self.name)

        for entry in maze.injuries_zones["bedside_nurse_waiting"][:]:
            if entry[1] == self.name:
                maze.injuries_zones["bedside_nurse_waiting"].remove(entry)
                break

        maze.patients_waiting_for_doctor[:] = [
            entry for entry in maze.patients_waiting_for_doctor
            if not (isinstance(entry, (list, tuple)) and len(entry) >= 2 and str(entry[1]).strip() == self.name)
        ]

        self._release_bed(maze)
        assigned_doctor = personas.get(str(self.scratch.assigned_doctor), None)
        if assigned_doctor:
            assigned_doctor.remove_patient(self, maze)
            # Ensure the doctor won't keep trying to see a patient who has left.
            queue = getattr(assigned_doctor.scratch, "assigned_patients_waitlist", None)
            if isinstance(queue, list):
                queue[:] = [
                    entry
                    for entry in queue
                    if not (
                        isinstance(entry, (list, tuple))
                        and len(entry) >= 2
                        and str(entry[1]).strip() == self.name
                    )
                ]

        for entry in maze.injuries_zones["assessment_queue"][:]:
            if entry[1] == self.name:
                maze.injuries_zones["assessment_queue"].remove(entry)
                break


    def _stay_after_discharge(self, maze):
        """
        Keep a discharged patient in their bed space for additional time.
        """
        zone = self.scratch.injuries_zone or "waiting room"
        self.scratch.state = "DISCHARGED_WAITING"
        bed_target = self._target_bed(maze, zone)
        if bed_target:
            self.scratch.next_step = f"<tile> {bed_target}"
        else:
            self.scratch.next_step = f"ed map:emergency department:{zone}:bed"
        linger_start = self.scratch.curr_time or datetime.datetime.now()
        self.scratch.lingering_after_discharge = True
        self.scratch.linger_started_at = linger_start
        duration = getattr(self, "post_discharge_linger_minutes", 0) or 0
        if duration > 0:
            self.scratch.linger_duration_minutes = duration
            self.scratch.linger_end_time = linger_start + timedelta(minutes=duration)
        else:
            self.scratch.linger_duration_minutes = None
            self.scratch.linger_end_time = None
        self.scratch.linger_recorded = False


    # ------------------------------------------------------------------
    # Deterministic state transitions (called from doctor.move())
    # ------------------------------------------------------------------

    def do_initial_assessment(self, doctor, maze):
        """Transition after first doctor assessment — deterministic, no chat needed.
        Returns True if the transition was applied, False if already past this state."""
        if self.scratch.state != "WAITING_FOR_FIRST_ASSESSMENT":
            return False

        self.scratch.act_path_set = False
        self.scratch.initial_assessment_done = True
        self.stamp_first_doctor_contact(int(getattr(self, "runtime_step", 0) or 0))
        self.queue_conversation_event(self.EVENT_DOCTOR_FIRST_ASSESS)

        if self.scratch.stage2_minutes is None:
            self.scratch.stage2_minutes = 0
        # Baseline gate — surge extra is added when entering WAITING_FOR_RESULT
        self.scratch.disposition_ready_at = (
            self.scratch.curr_time
            + timedelta(minutes=float(self.scratch.stage2_minutes))
        )

        # Probabilistic testing decision based on CTAS
        ctas_key = str(self.scratch.CTAS) if self.scratch.CTAS else "3"
        test_prob = float(self.testing_probability_by_ctas.get(ctas_key, 0.5))

        if random.random() < test_prob:
            self.scratch.testing_kind = testing_kind_for_ctas(self.scratch.CTAS)
            self.scratch.state = "WAITING_FOR_TEST"
            self.scratch.next_room = "diagnostic room"
            self.queue_conversation_event(self.EVENT_TEST_ORDERED)
            memory_hook_manager = getattr(self, "auto_memory_hook_manager", None)
            if memory_hook_manager is not None:
                memory_hook_manager.record_next_slot(
                    self,
                    step=int(getattr(self, "runtime_step", 0) or 0),
                    sim_time=self.scratch.curr_time,
                    slot_name="testing",
                    owner_role="BedsideNurse",
                    reason="doctor_ordered_test",
                )
        else:
            # No test — enters WAITING_FOR_RESULT immediately, apply surge extra now
            self.scratch.testing_kind = None
            self.scratch.state = "WAITING_FOR_RESULT"
            self.scratch.time_to_next = self.scratch.curr_time
            surge_extra = float(self.scratch.stage2_surge_extra or 0)
            if surge_extra > 0:
                self.scratch.disposition_ready_at = (
                    max(self.scratch.disposition_ready_at or self.scratch.curr_time,
                        self.scratch.curr_time)
                    + timedelta(minutes=surge_extra)
                )
            memory_hook_manager = getattr(self, "auto_memory_hook_manager", None)
            if memory_hook_manager is not None:
                memory_hook_manager.record_next_slot(
                    self,
                    step=int(getattr(self, "runtime_step", 0) or 0),
                    sim_time=self.scratch.curr_time,
                    slot_name="disposition_review",
                    owner_role="Doctor",
                    reason="doctor_completed_initial_assessment_without_test",
                )

        return True

    def do_disposition(self, doctor, maze):
        """Transition after disposition visit — deterministic, no chat needed.
        Returns True if the transition was applied, False if already past this state."""
        if self.scratch.state != "WAITING_FOR_DOCTOR":
            return False

        if self.scratch.assigned_doctor and str(self.scratch.assigned_doctor) == doctor.name:
            doctor.remove_patient(self, maze)

        self.scratch.act_path_set = False
        self.scratch.disposition_done = True

        # Check if patient should be admitted to hospital (boarding)
        if self.simulate_hospital_admission and self.admission_probability_by_ctas:
            ctas_key = str(self.scratch.CTAS) if self.scratch.CTAS else "3"
            admit_prob = float(self.admission_probability_by_ctas.get(ctas_key, 0.0))
            admitted = random.random() < admit_prob
            if admitted:
                current_step = self._runtime_step()
                self.scratch.decision_to_admit_step = current_step
                self.scratch.decision_to_admit_minute = self._minute_for_step(current_step)
                self.scratch.admission_boarding_start = self.scratch.curr_time
                target = self._downstream_target()
                self.scratch.disposition_target = target
                response = self._request_downstream_transfer(target)
                if response is None:
                    self._legacy_random_boarding()
                elif response.status == "accepted":
                    self._apply_accepted_transfer(response, target)
                else:
                    self._apply_pending_transfer(response)
                utils.log_runtime_event(
                    "patient disposition entered downstream transfer flow",
                    sim_code=utils.static_sim_code,
                    extra={
                        "patient": self.name,
                        "ctas": self.scratch.CTAS,
                        "target": self.scratch.disposition_target,
                        "transfer_request_id": self.scratch.transfer_request_id,
                        "transfer_status": self.scratch.transfer_status,
                    },
                )
                memory_hook_manager = getattr(self, "auto_memory_hook_manager", None)
                if memory_hook_manager is not None:
                    memory_hook_manager.record_disposition_decided(
                        self,
                        step=current_step,
                        sim_time=self.scratch.curr_time,
                        disposition="admit",
                    )
                    memory_hook_manager.record_next_slot(
                        self,
                        step=current_step,
                        sim_time=self.scratch.curr_time,
                        slot_name="boarding",
                        owner_role="BedsideNurse",
                        reason="patient_admitted_to_hospital",
                    )
                return True

        if self.scratch.stage3_minutes is None:
            self.scratch.stage3_minutes = 0
        self.scratch.exit_ready_at = (
            self.scratch.curr_time
            + timedelta(minutes=float(self.scratch.stage3_minutes))
        )
        self.scratch.state = "WAITING_FOR_EXIT"
        self.scratch.disposition_status = "discharged"
        self.scratch.next_step = (
            f"ed map:emergency department:{self.scratch.injuries_zone}:bed"
        )
        self.queue_conversation_event(self.EVENT_DISPOSITION_CHANGED)
        if (
            self.post_discharge_linger_probability > 0
            and random.random() <= self.post_discharge_linger_probability
        ):
            self._stay_after_discharge(maze)
        memory_hook_manager = getattr(self, "auto_memory_hook_manager", None)
        if memory_hook_manager is not None:
            memory_hook_manager.record_disposition_decided(
                self,
                step=int(getattr(self, "runtime_step", 0) or 0),
                sim_time=self.scratch.curr_time,
                disposition="discharge",
            )
            memory_hook_manager.record_next_slot(
                self,
                step=int(getattr(self, "runtime_step", 0) or 0),
                sim_time=self.scratch.curr_time,
                slot_name="exit",
                owner_role="Patient",
                reason="patient_ready_for_exit",
            )

        return True

    def react_to_chat(self, convo_summary, other_persona, maze):
        self.scratch.act_path_set = False
        if(other_persona.role == "TriageNurse"):
            # While only in the traige assessment state
            if(self.scratch.state == "TRIAGE"):
                self.consume_active_conversation_event()
                self.stamp_triage_completed(int(getattr(self, "runtime_step", 0) or 0))
                # If talking to Triage Nurse assigned the next room to go to for the Bedside Nurse to take them there 
                self.scratch.next_room = self.scratch.injuries_zone

                self.scratch.state = "WAITING_FOR_NURSE"
                self.mark_handoff()
                memory_hook_manager = getattr(self, "auto_memory_hook_manager", None)
                if memory_hook_manager is not None:
                    memory_hook_manager.record_handoff_requested(
                        self,
                        step=int(getattr(self, "runtime_step", 0) or 0),
                        sim_time=self.scratch.curr_time,
                        from_role="TriageNurse",
                        to_role="BedsideNurse",
                        reason=f"transfer_to_{self.scratch.next_room or 'care_zone'}",
                    )
                    memory_hook_manager.record_next_slot(
                        self,
                        step=int(getattr(self, "runtime_step", 0) or 0),
                        sim_time=self.scratch.curr_time,
                        slot_name="bedside_transfer",
                        owner_role="BedsideNurse",
                        reason="triage_completed_waiting_for_bedside_transfer",
                    )

                self.scratch.next_step = "ed map:emergency department:waiting room:waiting room chair"
                
        elif(other_persona.role == "BedsideNurse"):
            self.consume_active_conversation_event()
            # State transitions are now handled deterministically when the
            # nurse picks the patient from the queue.  This block is kept as
            # an idempotent fallback — if the transition already happened,
            # the guard condition prevents double-firing.
            if(self.scratch.next_room and self.scratch.state == "WAITING_FOR_NURSE"):
                bed_target = self._target_bed(maze, self.scratch.next_room)
                if bed_target:
                    self.scratch.next_step = f"<tile> {bed_target}"
                else:
                    self.scratch.next_step = f"ed map:emergency department:{self.scratch.next_room}:bed"
                self.scratch.state = "WAITING_FOR_FIRST_ASSESSMENT"
                # Surge extra: push the assessment gate forward so
                # the surge slowdown is experienced in-bed.
                surge_extra = float(self.scratch.stage1_surge_extra or 0)
                if surge_extra > 0:
                    self.scratch.initial_assessment_ready_at = (
                        max(self.scratch.initial_assessment_ready_at or self.scratch.curr_time,
                            self.scratch.curr_time)
                        + timedelta(minutes=surge_extra)
                    )
                memory_hook_manager = getattr(self, "auto_memory_hook_manager", None)
                if memory_hook_manager is not None:
                    memory_hook_manager.record_handoff_completed(
                        self,
                        step=int(getattr(self, "runtime_step", 0) or 0),
                        sim_time=self.scratch.curr_time,
                        from_role="TriageNurse",
                        to_role="BedsideNurse",
                        completion_note="patient_transferred_to_care_zone",
                    )
                    memory_hook_manager.record_next_slot(
                        self,
                        step=int(getattr(self, "runtime_step", 0) or 0),
                        sim_time=self.scratch.curr_time,
                        slot_name="doctor_first_assessment",
                        owner_role="Doctor",
                        reason="patient_arrived_in_bed_for_first_assessment",
                    )

        elif(other_persona.role == "Doctor"):
            self.consume_active_conversation_event()
            # State transitions are now handled deterministically when the
            # doctor selects the patient from their waitlist.  These calls
            # are idempotent — they check current state before acting.
            self.do_initial_assessment(other_persona, maze)
            self.do_disposition(other_persona, maze)



                




    # Get Patient to go to Triage Room and talk to Triage Nurse
    def to_triage(self, triage_persona):
        self.scratch.next_step = f"<persona> {triage_persona.name}"
        # self.scratch.next_step = "ed map:emergency department:triage room:chair"
        self.scratch.state = "TRIAGE"
        self.queue_conversation_event(self.EVENT_TRIAGE_FIRST_CONTACT)

        self.scratch.act_path_set = False

    
    # Remove ability to iniate conversations
    def decide_to_chat(self, target_persona):
        return False

    # Initialize their section in the data_collection dict
    def data_collection_dict(self):
        temp_dict = {}

        temp_dict["ICD-10-CA_code"] = ""
        temp_dict["CTAS_score"] = ""
        temp_dict["injuries_zone"] = ""
        temp_dict["time_spent_area"] = {}
        temp_dict["time_spent_state"] = {}
        temp_dict["tiles_traveled"] = 0
        temp_dict["travel_time_minutes"] = 0
        temp_dict["travel_time_state"] = {}
        temp_dict["travel_time_area"] = {}
        temp_dict["exempt_from_data_collection"] = self.scratch.exempt_from_data_collection
        temp_dict["left_department_by_choice"] = {"occurred": False}
        temp_dict["lingered_after_discharge"] = {"occurred": False}
        temp_dict["admitted_to_hospital"] = {"occurred": False}
        temp_dict["boarding_timeout_event"] = {"occurred": False}
        temp_dict["testing_kind"] = None
        temp_dict["queue_exposure"] = ensure_queue_exposure({})
        temp_dict["bedside_reinsert_count"] = int(getattr(self.scratch, "bedside_reinsert_count", 0) or 0)
        return temp_dict
    
    # Put their data in the data_collection dict
    def save_data(self, dict):
        if self.scratch.triage_completed_minute is None and self.scratch.state not in {"WAITING_FOR_TRIAGE", "TRIAGE"}:
            fallback_step = self.scratch.first_doctor_contact_step
            if fallback_step is None:
                fallback_step = int(getattr(self, "runtime_step", 0) or 0)
            self.stamp_triage_completed(int(fallback_step))

        dict["ICD-10-CA_code"] = self.scratch.ICD
        dict["CTAS_score"] = self.scratch.CTAS
        dict["injuries_zone"] = self.scratch.injuries_zone
        dict["stage1_minutes"] = (self.scratch.stage1_minutes or 0) + (self.scratch.stage1_surge_extra or 0)
        dict["stage2_minutes"] = (self.scratch.stage2_minutes or 0) + (self.scratch.stage2_surge_extra or 0)
        dict["stage3_minutes"] = self.scratch.stage3_minutes
        dict["testing_kind"] = self.scratch.testing_kind
        dict["ed_arrival_step"] = self.scratch.ed_arrival_step
        dict["ed_arrival_minute"] = self.scratch.ed_arrival_minute
        dict["ed_arrival_at"] = self.scratch.ed_arrival_minute
        dict["triage_completed_step"] = self.scratch.triage_completed_step
        dict["triage_completed_minute"] = self.scratch.triage_completed_minute
        dict["triage_completed_at"] = self.scratch.triage_completed_minute
        dict["first_doctor_contact_step"] = self.scratch.first_doctor_contact_step
        dict["first_doctor_contact_minute"] = self.scratch.first_doctor_contact_minute
        dict["first_doctor_contact_at"] = self.scratch.first_doctor_contact_minute
        dict["ed_exit_step"] = self.scratch.ed_exit_step
        dict["ed_exit_minute"] = self.scratch.ed_exit_minute
        dict["ed_exit_at"] = self.scratch.ed_exit_minute
        dict["care_completed_step"] = self.scratch.care_completed_step
        dict["care_completed_minute"] = self.scratch.care_completed_minute
        dict["disposition_status"] = self.scratch.disposition_status
        dict["assigned_doctor"] = getattr(self.scratch, "assigned_doctor", None)
        dict["doctor_dispatch_policy_at_contact"] = getattr(self.scratch, "doctor_dispatch_policy_at_contact", None)
        dict["decision_to_admit_step"] = getattr(self.scratch, "decision_to_admit_step", None)
        dict["decision_to_admit_minute"] = getattr(self.scratch, "decision_to_admit_minute", None)
        dict["disposition_target"] = getattr(self.scratch, "disposition_target", None)
        dict["transfer_request_id"] = getattr(self.scratch, "transfer_request_id", None)
        dict["transfer_status"] = getattr(self.scratch, "transfer_status", None)
        dict["boarding_started_step"] = getattr(self.scratch, "boarding_started_step", None)
        dict["boarding_started_minute"] = getattr(self.scratch, "boarding_started_minute", None)
        dict["ward_transfer_step"] = getattr(self.scratch, "ward_transfer_step", None)
        dict["ward_transfer_minute"] = getattr(self.scratch, "ward_transfer_minute", None)
        dict["icu_admit_step"] = getattr(self.scratch, "icu_admit_step", None)
        dict["icu_admit_minute"] = getattr(self.scratch, "icu_admit_minute", None)
        dict["boarding_timeout_step"] = getattr(self.scratch, "boarding_timeout_step", None)
        dict["boarding_timeout_minute"] = getattr(self.scratch, "boarding_timeout_minute", None)
        dict["queue_exposure"] = self.ensure_queue_exposure_payload()
        dict["bedside_reinsert_count"] = int(getattr(self.scratch, "bedside_reinsert_count", 0) or 0)
        dict["time_scale_minutes_per_step"] = self._minutes_per_step()

        walkout_entry = dict.setdefault("left_department_by_choice", {"occurred": False})
        if self.scratch.left_without_being_seen:
            walkout_entry.update({
                "occurred": True,
                "state": self.scratch.left_without_being_seen_state,
                "wait_minutes": self.scratch.left_without_being_seen_wait_minutes,
                "timestamp": (self.scratch.left_without_being_seen_time.strftime("%B %d, %Y, %H:%M:%S")
                              if self.scratch.left_without_being_seen_time else None),
            })
        else:
            walkout_entry.setdefault("occurred", False)

        linger_entry = dict.setdefault("lingered_after_discharge", {"occurred": False})
        if self.scratch.linger_started_at:
            linger_entry.update({
                "occurred": True,
                "decided_at": self.scratch.linger_started_at.strftime("%B %d, %Y, %H:%M:%S"),
                "expected_duration_minutes": self.scratch.linger_duration_minutes,
                "ended_at": (self.scratch.linger_end_time.strftime("%B %d, %Y, %H:%M:%S")
                             if self.scratch.linger_end_time and not self.scratch.lingering_after_discharge else None),
            })
        else:
            linger_entry.setdefault("occurred", False)

        admission_entry = dict.setdefault("admitted_to_hospital", {"occurred": False})
        if self.scratch.admitted_to_hospital:
            boarding_duration = None
            if self.scratch.admission_boarding_start and self.scratch.admission_boarding_end:
                boarding_duration = (self.scratch.admission_boarding_end - self.scratch.admission_boarding_start).total_seconds() / 60
            admission_entry.update({
                "occurred": True,
                "boarding_start": (self.scratch.admission_boarding_start.strftime("%B %d, %Y, %H:%M:%S")
                                   if self.scratch.admission_boarding_start else None),
                "boarding_end": (self.scratch.admission_boarding_end.strftime("%B %d, %Y, %H:%M:%S")
                                 if self.scratch.admission_boarding_end else None),
                "boarding_duration_minutes": boarding_duration,
                "decision_to_admit_minute": getattr(self.scratch, "decision_to_admit_minute", None),
                "disposition_target": getattr(self.scratch, "disposition_target", None),
                "transfer_request_id": getattr(self.scratch, "transfer_request_id", None),
                "transfer_status": getattr(self.scratch, "transfer_status", None),
            })
        else:
            admission_entry.setdefault("occurred", False)

        timeout_entry = dict.setdefault("boarding_timeout_event", {"occurred": False})
        if self.scratch.boarding_timeout_recorded:
            timeout_entry.update({
                "occurred": True,
                "timestamp": (self.scratch.boarding_timeout_at.strftime("%B %d, %Y, %H:%M:%S")
                              if self.scratch.boarding_timeout_at else None),
                "threshold_minutes": float(self.boarding_timeout_minutes),
                "minute": getattr(self.scratch, "boarding_timeout_minute", None),
            })
        else:
            timeout_entry.setdefault("occurred", False)

        return dict
    
    # For when you want to get a location of a spawn location
    def get_spawn_loc(self, maze):
        return random.choice(list(maze.address_tiles["<spawn_loc>exit"]))

    def leave_ed(self, maze, personas, sim_folder, data_collection=None):
        persona_key = self.name
        if self.scratch.admitted_to_hospital:
            self.stamp_ed_exit(int(getattr(self, "runtime_step", 0) or 0), "admitted_and_transferred")
        elif self.scratch.left_without_being_seen:
            self.stamp_ed_exit(int(getattr(self, "runtime_step", 0) or 0), "left_without_being_seen")
        else:
            self.stamp_ed_exit(int(getattr(self, "runtime_step", 0) or 0), "discharged")

        # --- Full cleanup from all queues and zones ---
        # Triage queue
        if self.name in maze.triage_queue:
            maze.triage_queue.remove(self.name)
        self._release_testing_resources(maze)
        # Bedside nurse waiting queue
        for entry in maze.injuries_zones.get("bedside_nurse_waiting", [])[:]:
            if entry[1] == self.name:
                maze.injuries_zones["bedside_nurse_waiting"].remove(entry)
                break
        # Assessment queue
        for entry in maze.injuries_zones.get("assessment_queue", [])[:]:
            if entry[1] == self.name:
                maze.injuries_zones["assessment_queue"].remove(entry)
                break
        # Diagnostic room current_patients
        diag_patients = maze.injuries_zones.get("diagnostic room", {}).get("current_patients", [])
        if self.name in diag_patients:
            diag_patients.remove(self.name)
        # All injury zone current_patients
        for zone_name, zone_info in maze.injuries_zones.items():
            if isinstance(zone_info, dict):
                cp = zone_info.get("current_patients", [])
                if self.name in cp:
                    cp.remove(self.name)
        # Clear any bedside nurse occupied reference
        for p in personas.values():
            if getattr(p, 'role', None) == 'BedsideNurse':
                occ = getattr(p.scratch, 'occupied', None)
                if occ and self.name in str(occ):
                    p.scratch.occupied = None
                    p.scratch.next_step = None
                    p.scratch.act_path_set = False

        # Ensure bed capacity is freed and the patient is removed from zone tracking.
        self._release_bed(maze)

        maze.patients_waiting_for_doctor[:] = [
            entry for entry in maze.patients_waiting_for_doctor
            if not (isinstance(entry, (list, tuple)) and len(entry) >= 2 and str(entry[1]).strip() == self.name)
        ]

        # Ensure the doctor won't keep tracking / queuing this patient.
        assigned_doctor = personas.get(str(self.scratch.assigned_doctor), None)
        if assigned_doctor:
            assigned_doctor.remove_patient(self, maze)
            queue = getattr(assigned_doctor.scratch, "assigned_patients_waitlist", None)
            if isinstance(queue, list):
                queue[:] = [
                    entry
                    for entry in queue
                    if not (
                        isinstance(entry, (list, tuple))
                        and len(entry) >= 2
                        and str(entry[1]).strip() == self.name
                    )
                ]

        # Save info to scratch file
        self.save(f"{sim_folder}/personas/{persona_key}/bootstrap_memory")

        # Persist a final snapshot into the shared data collection (reverie.py owns it).
        if data_collection is not None:
            role_bucket = data_collection.setdefault(self.role, {})
            persona_bucket = role_bucket.get(persona_key)
            if persona_bucket is None:
                persona_bucket = self.data_collection_dict()
            role_bucket[persona_key] = self.save_data(persona_bucket)
