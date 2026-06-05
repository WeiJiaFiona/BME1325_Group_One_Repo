import sys
import datetime
import json

sys.path.append('../../')
from persona.memory_structures.scratch import *
from global_methods import *

class patient_scratch(Scratch):
    def __init__(self, f_saved):
        super().__init__(f_saved)
        self.ICD = None
        self.CTAS = None
        self.next_room = None
        self.state = None
        self.time_to_next = None
        self.exempt_from_data_collection = False
        self.user_controlled = False
        self.user_patient_id = None
        self.user_encounter_id = None
        self.user_phase = None
        self.left_without_being_seen = False
        self.left_without_being_seen_time = None
        self.left_without_being_seen_state = None
        self.left_without_being_seen_wait_minutes = None
        self.walkout_last_check_minute = 0.0
        self.walkout_recorded = False
        self.lingering_after_discharge = False
        self.linger_started_at = None
        self.linger_end_time = None
        self.linger_duration_minutes = None
        self.linger_recorded = False
        self.bed_assignment = None
        self.initial_assessment_ready_at = None
        self.disposition_ready_at = None
        self.exit_ready_at = None
        self.stage1_minutes = None
        self.stage1_surge_extra = None
        self.stage2_minutes = None
        self.stage2_surge_extra = None
        self.stage3_minutes = None
        self.initial_assessment_done = False
        self.disposition_done = False
        self.in_queue = False
        self.assigned_doctor = None
        self.preload_departure_at = None
        self.testing_end_time = None
        self.testing_kind = None
        self.admitted_to_hospital = False
        self.admission_boarding_start = None
        self.admission_boarding_end = None
        self.boarding_timeout_recorded = False
        self.boarding_timeout_at = None
        self.decision_to_admit_step = None
        self.decision_to_admit_minute = None
        self.disposition_target = None
        self.transfer_request_id = None
        self.transfer_status = None
        self.transfer_next_check_step = None
        self.transfer_next_check_minute = None
        self.transfer_completed_step = None
        self.transfer_completed_minute = None
        self.assigned_downstream_bed = None
        self.boarding_started_step = None
        self.boarding_started_minute = None
        self.ward_transfer_step = None
        self.ward_transfer_minute = None
        self.icu_admit_step = None
        self.icu_admit_minute = None
        self.boarding_timeout_step = None
        self.boarding_timeout_minute = None
        self.last_conversation_step = None
        self.conversation_cooldown_steps = 2
        self.last_conversation_event = None
        self.last_handoff_step = None
        self.last_result_notified_at = None
        self.pending_conversation_events = []
        self.active_conversation_event = None
        self.time_scale_minutes_per_step = 1
        self.ed_arrival_step = None
        self.ed_arrival_minute = None
        self.triage_completed_step = None
        self.triage_completed_minute = None
        self.first_doctor_contact_step = None
        self.first_doctor_contact_minute = None
        self.ed_exit_step = None
        self.ed_exit_minute = None
        self.care_completed_step = None
        self.care_completed_minute = None
        self.disposition_status = None
        self.queue_exposure = {
            "doctor": {"max_queue_len": 0, "exposure_minutes": 0},
            "lab": {"max_queue_len": 0, "exposure_minutes": 0},
            "imaging": {"max_queue_len": 0, "exposure_minutes": 0},
            "bedside_nurse": {"max_queue_len": 0, "exposure_minutes": 0},
        }
        if check_if_file_exists(f_saved):

            scratch_load = json.load(open(f_saved))
            
            self.ICD =  scratch_load["ICD"]
            self.CTAS = scratch_load["CTAS"]
            self.next_room = scratch_load["next_room"]
            self.state = scratch_load["state"]
            # self.injuries_zone = scratch_load["injuries_zone"]
            self.injuries_zone = scratch_load.get("injuries_zone")
            if scratch_load["time_to_next"]: 
                self.time_to_next = datetime.datetime.strptime(scratch_load["time_to_next"],
                                                            "%B %d, %Y, %H:%M:%S")
                
            self.exempt_from_data_collection = scratch_load["exempt_from_data_collection"]
            self.user_controlled = scratch_load.get("user_controlled", False)
            self.user_patient_id = scratch_load.get("user_patient_id")
            self.user_encounter_id = scratch_load.get("user_encounter_id")
            self.user_phase = scratch_load.get("user_phase")
            self.left_without_being_seen = scratch_load.get("left_without_being_seen", False)
            left_time = scratch_load.get("left_without_being_seen_time")
            if left_time:
                self.left_without_being_seen_time = datetime.datetime.strptime(left_time, "%B %d, %Y, %H:%M:%S")
            self.left_without_being_seen_state = scratch_load.get("left_without_being_seen_state")
            self.left_without_being_seen_wait_minutes = scratch_load.get("left_without_being_seen_wait_minutes")
            self.walkout_last_check_minute = scratch_load.get("walkout_last_check_minute", 0.0)
            self.walkout_recorded = scratch_load.get("walkout_recorded", False)

            self.lingering_after_discharge = scratch_load.get("lingering_after_discharge", False)
            linger_start = scratch_load.get("linger_started_at")
            if linger_start:
                self.linger_started_at = datetime.datetime.strptime(linger_start, "%B %d, %Y, %H:%M:%S")
            linger_end = scratch_load.get("linger_end_time")
            if linger_end:
                self.linger_end_time = datetime.datetime.strptime(linger_end, "%B %d, %Y, %H:%M:%S")

                self.linger_duration_minutes = scratch_load.get("linger_duration_minutes")
                self.linger_recorded = scratch_load.get("linger_recorded", False)
            self.bed_assignment = scratch_load.get("bed_assignment")

            ia_ready = scratch_load.get("initial_assessment_ready_at")
            if ia_ready:
                self.initial_assessment_ready_at = datetime.datetime.strptime(ia_ready, "%B %d, %Y, %H:%M:%S")
            disp_ready = scratch_load.get("disposition_ready_at")
            if disp_ready:
                self.disposition_ready_at = datetime.datetime.strptime(disp_ready, "%B %d, %Y, %H:%M:%S")
            exit_ready = scratch_load.get("exit_ready_at")
            if exit_ready:
                self.exit_ready_at = datetime.datetime.strptime(exit_ready, "%B %d, %Y, %H:%M:%S")
            self.stage1_minutes = scratch_load.get("stage1_minutes")
            self.stage1_surge_extra = scratch_load.get("stage1_surge_extra")
            self.stage2_minutes = scratch_load.get("stage2_minutes")
            self.stage2_surge_extra = scratch_load.get("stage2_surge_extra")
            self.stage3_minutes = scratch_load.get("stage3_minutes")
            self.initial_assessment_done = scratch_load.get("initial_assessment_done", False)
            self.disposition_done = scratch_load.get("disposition_done", False)
            self.in_queue = scratch_load.get("in_queue", False)
            self.assigned_doctor = scratch_load.get("assigned_doctor", None)
            preload_dep = scratch_load.get("preload_departure_at")
            if preload_dep:
                self.preload_departure_at = datetime.datetime.strptime(preload_dep, "%B %d, %Y, %H:%M:%S")
            testing_end = scratch_load.get("testing_end_time")
            if testing_end:
                self.testing_end_time = datetime.datetime.strptime(testing_end, "%B %d, %Y, %H:%M:%S")
            self.testing_kind = scratch_load.get("testing_kind")

            self.admitted_to_hospital = scratch_load.get("admitted_to_hospital", False)
            boarding_start = scratch_load.get("admission_boarding_start")
            if boarding_start:
                self.admission_boarding_start = datetime.datetime.strptime(boarding_start, "%B %d, %Y, %H:%M:%S")
            boarding_end = scratch_load.get("admission_boarding_end")
            if boarding_end:
                self.admission_boarding_end = datetime.datetime.strptime(boarding_end, "%B %d, %Y, %H:%M:%S")
            self.boarding_timeout_recorded = scratch_load.get("boarding_timeout_recorded", False)
            boarding_timeout_at = scratch_load.get("boarding_timeout_at")
            if boarding_timeout_at:
                self.boarding_timeout_at = datetime.datetime.strptime(boarding_timeout_at, "%B %d, %Y, %H:%M:%S")
            self.decision_to_admit_step = scratch_load.get("decision_to_admit_step")
            self.decision_to_admit_minute = scratch_load.get("decision_to_admit_minute")
            self.disposition_target = scratch_load.get("disposition_target")
            self.transfer_request_id = scratch_load.get("transfer_request_id")
            self.transfer_status = scratch_load.get("transfer_status")
            self.transfer_next_check_step = scratch_load.get("transfer_next_check_step")
            self.transfer_next_check_minute = scratch_load.get("transfer_next_check_minute")
            self.transfer_completed_step = scratch_load.get("transfer_completed_step")
            self.transfer_completed_minute = scratch_load.get("transfer_completed_minute")
            self.assigned_downstream_bed = scratch_load.get("assigned_downstream_bed")
            self.boarding_started_step = scratch_load.get("boarding_started_step")
            self.boarding_started_minute = scratch_load.get("boarding_started_minute")
            self.ward_transfer_step = scratch_load.get("ward_transfer_step")
            self.ward_transfer_minute = scratch_load.get("ward_transfer_minute")
            self.icu_admit_step = scratch_load.get("icu_admit_step")
            self.icu_admit_minute = scratch_load.get("icu_admit_minute")
            self.boarding_timeout_step = scratch_load.get("boarding_timeout_step")
            self.boarding_timeout_minute = scratch_load.get("boarding_timeout_minute")
            self.last_conversation_step = scratch_load.get("last_conversation_step")
            self.conversation_cooldown_steps = scratch_load.get("conversation_cooldown_steps", 2)
            self.last_conversation_event = scratch_load.get("last_conversation_event")
            self.last_handoff_step = scratch_load.get("last_handoff_step")
            last_result_notified_at = scratch_load.get("last_result_notified_at")
            if last_result_notified_at:
                self.last_result_notified_at = datetime.datetime.strptime(last_result_notified_at, "%B %d, %Y, %H:%M:%S")
            self.pending_conversation_events = scratch_load.get("pending_conversation_events", [])
            self.active_conversation_event = scratch_load.get("active_conversation_event")
            self.time_scale_minutes_per_step = scratch_load.get("time_scale_minutes_per_step", 1)
            self.ed_arrival_step = scratch_load.get("ed_arrival_step")
            self.ed_arrival_minute = scratch_load.get("ed_arrival_minute")
            self.triage_completed_step = scratch_load.get("triage_completed_step")
            self.triage_completed_minute = scratch_load.get("triage_completed_minute")
            self.first_doctor_contact_step = scratch_load.get("first_doctor_contact_step")
            self.first_doctor_contact_minute = scratch_load.get("first_doctor_contact_minute")
            self.ed_exit_step = scratch_load.get("ed_exit_step")
            self.ed_exit_minute = scratch_load.get("ed_exit_minute")
            self.care_completed_step = scratch_load.get("care_completed_step")
            self.care_completed_minute = scratch_load.get("care_completed_minute")
            self.disposition_status = scratch_load.get("disposition_status")
            self.queue_exposure = scratch_load.get("queue_exposure", self.queue_exposure)

    def save(self, out_json):
        scratch = super().save(out_json)
        scratch["ICD"] = self.ICD
        scratch["CTAS"] = self.CTAS 
        scratch["next_room"] = self.next_room
        scratch["state"] = self.state
        scratch["injuries_zone"] = self.injuries_zone

        if self.time_to_next:
            scratch["time_to_next"] = (self.time_to_next
                                        .strftime("%B %d, %Y, %H:%M:%S"))
        else:
            scratch["time_to_next"] = None

        scratch["exempt_from_data_collection"] = self.exempt_from_data_collection
        scratch["user_controlled"] = self.user_controlled
        scratch["user_patient_id"] = self.user_patient_id
        scratch["user_encounter_id"] = self.user_encounter_id
        scratch["user_phase"] = self.user_phase
        scratch["left_without_being_seen"] = self.left_without_being_seen
        scratch["left_without_being_seen_time"] = (self.left_without_being_seen_time.strftime("%B %d, %Y, %H:%M:%S")
                                                   if self.left_without_being_seen_time else None)
        scratch["left_without_being_seen_state"] = self.left_without_being_seen_state
        scratch["left_without_being_seen_wait_minutes"] = self.left_without_being_seen_wait_minutes
        scratch["walkout_last_check_minute"] = self.walkout_last_check_minute
        scratch["walkout_recorded"] = self.walkout_recorded
        scratch["lingering_after_discharge"] = self.lingering_after_discharge
        scratch["linger_started_at"] = (self.linger_started_at.strftime("%B %d, %Y, %H:%M:%S")
                                        if self.linger_started_at else None)
        scratch["linger_end_time"] = (self.linger_end_time.strftime("%B %d, %Y, %H:%M:%S")
                                      if self.linger_end_time else None)
        scratch["linger_duration_minutes"] = self.linger_duration_minutes
        scratch["linger_recorded"] = self.linger_recorded
        scratch["bed_assignment"] = self.bed_assignment
        scratch["initial_assessment_ready_at"] = (self.initial_assessment_ready_at.strftime("%B %d, %Y, %H:%M:%S")
                                                 if self.initial_assessment_ready_at else None)
        scratch["disposition_ready_at"] = (self.disposition_ready_at.strftime("%B %d, %Y, %H:%M:%S")
                                           if self.disposition_ready_at else None)
        scratch["exit_ready_at"] = (self.exit_ready_at.strftime("%B %d, %Y, %H:%M:%S")
                                    if self.exit_ready_at else None)
        scratch["stage1_minutes"] = self.stage1_minutes
        scratch["stage1_surge_extra"] = self.stage1_surge_extra
        scratch["stage2_minutes"] = self.stage2_minutes
        scratch["stage2_surge_extra"] = self.stage2_surge_extra
        scratch["stage3_minutes"] = self.stage3_minutes
        scratch["initial_assessment_done"] = self.initial_assessment_done
        scratch["disposition_done"] = self.disposition_done
        scratch["in_queue"] = self.in_queue
        scratch["assigned_doctor"] = self.assigned_doctor
        scratch["preload_departure_at"] = (self.preload_departure_at.strftime("%B %d, %Y, %H:%M:%S")
                                           if self.preload_departure_at else None)
        scratch["testing_end_time"] = (self.testing_end_time.strftime("%B %d, %Y, %H:%M:%S")
                                       if self.testing_end_time else None)
        scratch["testing_kind"] = self.testing_kind
        scratch["admitted_to_hospital"] = self.admitted_to_hospital
        scratch["admission_boarding_start"] = (self.admission_boarding_start.strftime("%B %d, %Y, %H:%M:%S")
                                               if self.admission_boarding_start else None)
        scratch["admission_boarding_end"] = (self.admission_boarding_end.strftime("%B %d, %Y, %H:%M:%S")
                                              if self.admission_boarding_end else None)
        scratch["boarding_timeout_recorded"] = self.boarding_timeout_recorded
        scratch["boarding_timeout_at"] = (self.boarding_timeout_at.strftime("%B %d, %Y, %H:%M:%S")
                                          if self.boarding_timeout_at else None)
        scratch["decision_to_admit_step"] = self.decision_to_admit_step
        scratch["decision_to_admit_minute"] = self.decision_to_admit_minute
        scratch["disposition_target"] = self.disposition_target
        scratch["transfer_request_id"] = self.transfer_request_id
        scratch["transfer_status"] = self.transfer_status
        scratch["transfer_next_check_step"] = self.transfer_next_check_step
        scratch["transfer_next_check_minute"] = self.transfer_next_check_minute
        scratch["transfer_completed_step"] = self.transfer_completed_step
        scratch["transfer_completed_minute"] = self.transfer_completed_minute
        scratch["assigned_downstream_bed"] = self.assigned_downstream_bed
        scratch["boarding_started_step"] = self.boarding_started_step
        scratch["boarding_started_minute"] = self.boarding_started_minute
        scratch["ward_transfer_step"] = self.ward_transfer_step
        scratch["ward_transfer_minute"] = self.ward_transfer_minute
        scratch["icu_admit_step"] = self.icu_admit_step
        scratch["icu_admit_minute"] = self.icu_admit_minute
        scratch["boarding_timeout_step"] = self.boarding_timeout_step
        scratch["boarding_timeout_minute"] = self.boarding_timeout_minute
        scratch["last_conversation_step"] = self.last_conversation_step
        scratch["conversation_cooldown_steps"] = self.conversation_cooldown_steps
        scratch["last_conversation_event"] = self.last_conversation_event
        scratch["last_handoff_step"] = self.last_handoff_step
        scratch["last_result_notified_at"] = (self.last_result_notified_at.strftime("%B %d, %Y, %H:%M:%S")
                                              if self.last_result_notified_at else None)
        scratch["pending_conversation_events"] = self.pending_conversation_events
        scratch["active_conversation_event"] = self.active_conversation_event
        scratch["time_scale_minutes_per_step"] = self.time_scale_minutes_per_step
        scratch["ed_arrival_step"] = self.ed_arrival_step
        scratch["ed_arrival_minute"] = self.ed_arrival_minute
        scratch["triage_completed_step"] = self.triage_completed_step
        scratch["triage_completed_minute"] = self.triage_completed_minute
        scratch["first_doctor_contact_step"] = self.first_doctor_contact_step
        scratch["first_doctor_contact_minute"] = self.first_doctor_contact_minute
        scratch["ed_exit_step"] = self.ed_exit_step
        scratch["ed_exit_minute"] = self.ed_exit_minute
        scratch["care_completed_step"] = self.care_completed_step
        scratch["care_completed_minute"] = self.care_completed_minute
        scratch["disposition_status"] = self.disposition_status
        scratch["queue_exposure"] = self.queue_exposure
        with open(out_json, "w") as outfile:
            json.dump(scratch, outfile, indent=2)  
