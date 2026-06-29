
import datetime
import math
import random 
import sys
import time
import heapq
import bisect
import utils
sys.path.append('../../')
from persona.persona import *
from persona.memory_structures.scratch_types.triage_nurse_scratch import *
from bedside_queue_guards import guarded_bedside_reinsert
from ed_priority import queue_patient_priority_key, patient_ctas_level

class Triage_Nurse(Persona):
    priority_factor = 0
    def __init__(self, name, folder_mem_saved=False, role=None, seed=0):
        super().__init__(name,folder_mem_saved,role,seed)
        scratch_saved = f"{folder_mem_saved}/bootstrap_memory/scratch.json"
        self.scratch = triage_nurse_scratch(scratch_saved)

    def _should_skip_cognition(self):
        """Skip LLM perceive/retrieve/plan when the triage nurse is
        already in a conversation."""
        if self.scratch.chatting_with:
            return True
        return False

    def move(self, maze, personas, curr_tile, curr_time, data_collection):
        plan = super().move(maze, personas, curr_tile, curr_time, data_collection)

        # Validate chatting_patient still exists in the simulation
        if self.scratch.chatting_patient and self.scratch.chatting_patient not in personas:
            print(f"(TriageNurse) {self.name}: clearing stale chatting_patient={self.scratch.chatting_patient}")
            self.scratch.chatting_patient = None

        # Special condition for patient to do whatever the medical staff tells them. next_step changed in plan.py.
        # To easily control what a patient should do next in a given room

        # When the agent isn't talking to anyone control their movements or update state of world
        if(self.scratch.chatting_with == None):
            # If they had chatted to a patient add them to the waitlist for a bed
            if(self.scratch.chatting_patient):
                # Amount of patients in triage goes down
                if maze.triage_patients > 0:
                    maze.triage_patients -= 1
                print(self.scratch.chatting_patient)
                patient_name = self.scratch.chatting_patient
                patient = personas.get(patient_name)
                if patient:
                    data_collection.setdefault("Patients_Attended", []).append(
                        {
                            "step": int(getattr(self, "runtime_step", 0) or 0),
                            "time": curr_time.strftime("%B %d, %Y, %H:%M:%S") if curr_time else None,
                            "patient": patient_name,
                        }
                    )
                    if hasattr(patient, "stamp_triage_completed"):
                        patient.stamp_triage_completed(int(getattr(patient, "runtime_step", 0) or 0))
                    ctas = patient.scratch.CTAS if patient.scratch.CTAS is not None else 3

                    # Critical patients (CTAS 1/2) bypass the normal bedside
                    # queue so burst-mode triage completions are not trapped
                    # behind lower-acuity transfers.
                    if ctas > 2:
                        inserted, reason = guarded_bedside_reinsert(
                            queue=maze.injuries_zones["bedside_nurse_waiting"],
                            patient=patient,
                            priority=ctas * self.priority_factor,
                            data_collection=None,
                            increment_reinsert_count=False,
                        )
                        if inserted:
                            print(f"(TriageNurse) queued {patient_name} in bedside_nurse_waiting")
                        elif reason == "reinsert_count_exceeded_warning":
                            print(f"(TriageNurse) warning - {patient_name} bedside reinsert_count exceeded 3; suppressing repeat reinsert")
                    # Critical patients go to the pager queue for immediate
                    # bedside pickup.
                    else:
                        bisect.insort_right(
                            maze.injuries_zones["pager"],
                            [ctas * self.priority_factor, patient.name]
                        )
                self.scratch.chatting_patient = None

            # Move patient into triage room when there is room to fit them
            if(maze.triage_queue != [] and maze.triage_patients < maze.triage_capacity):
                maze.triage_queue.sort(key=lambda patient_name: queue_patient_priority_key(patient_name, personas))
                # Pop according to unified ED CTAS priority discipline
                persona_name = maze.triage_queue.pop(0)
                patient = personas.get(persona_name)
                if patient:
                    data_collection.setdefault("Selection_Events", []).append(
                        {
                            "step": int(getattr(self, "runtime_step", 0) or 0),
                            "selector_role": "TriageNurse",
                            "selector": self.name,
                            "queue": "triage_queue",
                            "selected_patient": persona_name,
                            "selected_patient_ctas": patient_ctas_level(patient),
                            "candidate_ctas_order": [
                                patient_ctas_level(personas[name])
                                for name in maze.triage_queue[:5]
                                if name in personas
                            ],
                        }
                    )
                    patient.to_triage(self)
                    maze.triage_patients += 1
                self.scratch.next_step = f"<persona> {persona_name}"
            self.scratch.act_address = "ed map:emergency department:triage room:computer"
            plan = self.scratch.act_address
        return self.execute(maze, personas, plan)  

    def react_to_chat(self, convo_summary, other_persona, maze):
        if(other_persona.role == "Patient"):
            # While only in the triage room
            # To set up adding Patient to Bedside Nurse queue when done talking 
            if(other_persona.scratch.state == "TRIAGE"):
                self.scratch.chatting_patient = other_persona.name

    def decide_to_chat(self, target_persona):
        if(target_persona.role == "Patient"):
            if(
                target_persona.scratch.state == "TRIAGE"
                and hasattr(target_persona, "select_conversation_event")
                and target_persona.select_conversation_event([target_persona.EVENT_TRIAGE_FIRST_CONTACT])
            ):
                return True
            else:
                return False
        # No staff-to-staff conversations — skip LLM fallthrough
        return False
    def get_spawn_loc(self, maze):
        return list(maze.address_tiles[f"ed map:emergency department:triage room:chair"])[int(self.name.split(' ')[-1]) % len(maze.address_tiles["ed map:emergency department:triage room:chair"])] 

        # return random.choice(list(maze.address_tiles["<spawn_loc>triage room"]))
    #ed map:emergency department:triage room:chair

    def data_collection_dict(self):
        return {"Patients_Attended": []}
