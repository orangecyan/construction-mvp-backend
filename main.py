import os
import json
import random
import string
import csv
import codecs
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv
from groq import Groq
from templates import get_phase_structure 
from fastapi.middleware.cors import CORSMiddleware

# 1. SETUP
load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Construction Backend V8 (Full ERP)", "status": "Online"}

# ---------------------------------------------------------
# DATA MODELS
# ---------------------------------------------------------

class ProjectCreate(BaseModel):
    owner_id: str 
    name: str
    code: str
    project_type: str
    sub_type: str
    building_class: str
    construction_method: str = "Standard"
    delivery_method: str = "Design-Bid-Build"
    ownership_model: str = "For Sale"
    address_full: str
    num_floors: int = 1
    num_units: int = 1
    num_towers: int = 1
    built_up_area_sqft: float = 0.0
    has_parking: bool = False
    has_retail: bool = False
    basement_levels: int = 0
    site_context: str = "Greenfield"
    complexity: str = "Medium"
    sustainability_rating: str = "None"
    start_date_planned: str
    end_date_planned: Optional[str] = None
    priority: str = "Medium"
    permit_status: str = "Pending"
    jurisdiction: Optional[str] = None
    plan_urls: list[str] = [] 
    constraints: str = "Standard construction"

class ProjectRequest(BaseModel):
    name: str
    code: str
    project_type: str 
    project_subtype: str
    building_class: str
    construction_method: str
    delivery_method: str
    site_context: str
    sustainability_rating: str
    floors: int = 1
    location: str     
    start_date: str   
    constraints: str  

class JoinRequest(BaseModel):
    user_id: str 
    project_code: str

class ChatMessage(BaseModel):
    project_id: int
    user_id: str
    message: str
    context: str = "Execution" 

class LeadInput(BaseModel):
    project_id: int
    raw_input: str 
    source: str = "Manual"

class TeamMemberAdd(BaseModel):
    project_id: int
    email: str
    role: str
    department: str = "Execution" 
    access_level: str = "Partial" 
    employment_type: str = "Full-Time"
    skills: list[str] = []
    shift_start: str = "09:00"
    shift_end: str = "17:00"
    work_days: dict = {"mon":True, "tue":True, "wed":True, "thu":True, "fri":True, "sat":False, "sun":False}

class TaskAdd(BaseModel):
    stage_id: int
    parent_task_id: Optional[int] = None
    name: str
    assigned_role: str = "General"

class TaskUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    assigned_role: Optional[str] = None

class ScheduleRequest(BaseModel):
    project_id: int

# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------

def save_recursive_tasks(tasks_list, stage_id, parent_id=None):
    for task in tasks_list:
        task_data = {
            "stage_id": stage_id,
            "parent_task_id": parent_id,
            "name": task['task_name'],
            "assigned_role": task.get('assigned_role', 'General'),
            "status": "Not Started"
        }
        res = supabase.table("tasks").insert(task_data).execute()
        if res.data:
            current_task_id = res.data[0]['id']
            if 'subtasks' in task and task['subtasks']:
                save_recursive_tasks(task['subtasks'], stage_id, current_task_id)

def qualify_lead_with_ai(raw_text):
    prompt = f"""
    Act as a Real Estate Sales Manager. Analyze: "{raw_text}"
    Extract: Name, Phone, Email. Determine Intent, Score (0-100), and Next Action.
    Return JSON: {{ "extracted_data": {{...}}, "analysis": {{...}}, "scoring": {{...}}, "next_action": {{...}} }}
    """
    try:
        chat = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"}
        )
        return json.loads(chat.choices[0].message.content)
    except:
        return {"scoring": {"score": 0}}

# ---------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------

@app.post("/projects/create")
def create_project_full(req: ProjectCreate):
    data = req.dict()
    data["status"] = "Planning"
    proj_res = supabase.table("projects").insert(data).execute()
    if not proj_res.data: raise HTTPException(status_code=500, detail="Failed to create project")
    
    # Owner gets Full Access
    member_data = { 
        "project_id": proj_res.data[0]['id'], 
        "user_id": req.owner_id, 
        "role": "Owner", 
        "department": "Management", 
        "status": "Active" 
    }
    supabase.table("project_members").insert(member_data).execute()
    return {"status": "success", "project_id": proj_res.data[0]['id']}

@app.post("/projects/generate-schedule")
def generate_schedule(req: ProjectRequest):
    existing = supabase.table("projects").select("id").eq("code", req.code).execute()
    if existing.data:
        project_id = existing.data[0]['id']
    else:
        proj_res = supabase.table("projects").insert({"name": req.name, "code": req.code, "status": "Planning"}).execute()
        project_id = proj_res.data[0]['id']

    base_phases = get_phase_structure(req.project_type)
    prompt = f"""
    Act as a Senior US Construction Scheduler.
    PROJECT DNA: {req.dict()}
    GUIDELINE PHASES: {json.dumps(base_phases)}
    Generate WBS JSON. OUTPUT: {{ "schedule": [ {{ "stage_name": "...", "tasks": [ {{ "task_name": "...", "assigned_role": "..." }} ] }} ] }}
    """
    chat = groq_client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}], 
        model="llama-3.3-70b-versatile", 
        response_format={"type": "json_object"}
    )
    schedule_data = json.loads(chat.choices[0].message.content)

    for item in schedule_data['schedule']:
        stage_res = supabase.table("stages").insert({"project_id": project_id, "name": item['stage_name'], "status": "Scheduled"}).execute()
        if stage_res.data and 'tasks' in item:
            save_recursive_tasks(item['tasks'], stage_res.data[0]['id'])
    return {"status": "success", "project_id": project_id}

@app.get("/projects/{project_id}/dashboard")
def get_project_dashboard(project_id: int):
    proj = supabase.table("projects").select("*").eq("id", project_id).execute()
    # Updated: Order tasks by id to keep them stable
    data = supabase.table("stages").select("*, tasks(*)").eq("project_id", project_id).order("id").execute()
    if not proj.data: raise HTTPException(status_code=404, detail="Not found")
    return {"project": proj.data[0], "timeline_data": data.data}

@app.post("/projects/team/add")
def add_team_member(req: TeamMemberAdd):
    user_res = supabase.table("profiles").select("id").eq("email", req.email).execute()
    if not user_res.data: raise HTTPException(status_code=404, detail="User email not found")
    
    data = req.dict()
    del data['email']
    data['user_id'] = user_res.data[0]['id']
    data['status'] = 'Active'
    
    supabase.table("project_members").insert(data).execute()
    return {"status": "Member Added"}

# --- INTELLIGENT CHAT ---
@app.post("/chat/send")
def send_chat_update(req: ChatMessage):
    # 1. Log
    supabase.table("chat_logs").insert({
        "project_id": req.project_id, "user_id": req.user_id, "message_text": req.message
    }).execute()

    # 2. Context Aware Logic
    if req.context == "Execution":
        tasks_res = supabase.table("tasks").select("id, name, status").eq("project_id", req.project_id).execute()
        # Simplified context to avoid token limits
        task_context = [{"id": t['id'], "name": t['name'], "status": t['status']} for t in tasks_res.data[:30]]
        
        prompt = f"""
        User said: "{req.message}"
        Context: Project Tasks: {task_context}
        Goal: If user updates a task, return JSON: {{ "action": "UPDATE", "task_id": 123, "new_status": "Completed/In Progress", "reply": "Updated X to Y" }}
        If general question, return JSON: {{ "action": "REPLY", "reply": "Your answer" }}
        """
        try:
            chat = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}], 
                model="llama-3.3-70b-versatile", 
                response_format={"type": "json_object"}
            )
            res = json.loads(chat.choices[0].message.content)
            
            if res.get("action") == "UPDATE":
                supabase.table("tasks").update({"status": res["new_status"]}).eq("id", res["task_id"]).execute()
                return {"status": "Action Taken", "response": res.get("reply", "Task updated.")}
            else:
                return {"status": "Replied", "response": res.get("reply", "Understood.")}
        except: 
            return {"status": "Error", "response": "I didn't quite catch that update."}

    elif req.context == "Sales":
        ai_result = qualify_lead_with_ai(req.message)
        if ai_result.get("scoring", {}).get("score", 0) > 0: # Lower threshold to capture more
             extracted = ai_result.get("extracted_data", {})
             data = { 
                 "project_id": req.project_id, 
                 "name": extracted.get("name", "New Lead"), 
                 "phone": extracted.get("phone", ""), 
                 "email": extracted.get("email", ""),
                 "source": "Chat", 
                 "lead_score": ai_result["scoring"].get("score", 50), 
                 "ai_qualification": ai_result, 
                 "status": "New" 
             }
             supabase.table("leads").insert(data).execute()
             return {"status": "Lead Detected", "response": f"Added {data['name']} to pipeline (Score: {data['lead_score']})."}

    return {"status": "Message Logged", "response": "Message logged."}

# --- SMART SCHEDULER ---
@app.post("/projects/auto-schedule")
def auto_schedule(req: ScheduleRequest):
    # 1. Fetch unstarted tasks & team
    tasks = supabase.table("tasks").select("*").eq("project_id", req.project_id).eq("status", "Not Started").execute().data
    members = supabase.table("project_members").select("*").eq("project_id", req.project_id).execute().data
    
    if not tasks: return {"status": "No tasks to schedule"}
    if not members: return {"status": "No team members found"}

    # 2. AI Assignment
    prompt = f"""
    Act as Construction Scheduler.
    TASKS: {json.dumps([{'id': t['id'], 'name': t['name'], 'role': t['assigned_role']} for t in tasks])}
    TEAM: {json.dumps([{'id': m['user_id'], 'role': m['role'], 'skills': m['skills_tags']} for m in members])}
    Assign best member to task. Estimate hours (4-40).
    Return JSON: {{ "assignments": [ {{ "task_id": 123, "member_id": "uuid", "hours": 8 }} ] }}
    """
    
    try:
        chat = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"}
        )
        plan = json.loads(chat.choices[0].message.content)
        
        updates = 0
        current_date = datetime.now()
        
        for item in plan.get("assignments", []):
            if item.get("member_id"):
                days = max(1, item['hours'] // 8)
                end_date = current_date + timedelta(days=days)
                
                supabase.table("tasks").update({
                    "assigned_sub_id": item['member_id'],
                    "start_date": current_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d"),
                    "status": "In Progress" # Auto-start for MVP
                }).eq("id", item['task_id']).execute()
                updates += 1
                
        return {"status": "Scheduled", "tasks_updated": updates}
    except Exception as e:
        return {"status": "Error", "detail": str(e)}

# --- CSV UPLOAD ---
@app.post("/leads/upload-csv")
async def upload_leads_csv(project_id: int, file: UploadFile = File(...)):
    csv_reader = csv.DictReader(codecs.iterdecode(file.file, 'utf-8'))
    leads_to_insert = []
    
    for row in csv_reader:
        # Flexible key matching
        name = row.get("Name") or row.get("name") or "Unknown"
        phone = row.get("Phone") or row.get("phone")
        email = row.get("Email") or row.get("email")
        
        leads_to_insert.append({
            "project_id": project_id,
            "name": name,
            "phone": phone,
            "email": email,
            "source": "CSV Import",
            "status": "New",
            "lead_score": 50
        })
        
    if leads_to_insert:
        supabase.table("leads").insert(leads_to_insert).execute()
        
    return {"status": "Success", "count": len(leads_to_insert)}

# ... (Tasks/CRUD Endpoints remain mostly same) ...

@app.post("/tasks/add")
def add_task(req: TaskAdd):
    # Added project_id logic by fetching stage
    stage = supabase.table("stages").select("project_id").eq("id", req.stage_id).single().execute()
    data = {
        "project_id": stage.data['project_id'], # Important for context
        "stage_id": req.stage_id, "parent_task_id": req.parent_task_id, 
        "name": req.name, "assigned_role": req.assigned_role, "status": "Not Started"
    }
    supabase.table("tasks").insert(data).execute()
    return {"status": "added"}

@app.patch("/tasks/{task_id}")
def update_task(task_id: int, req: TaskUpdate):
    data = {k: v for k, v in req.dict().items() if v is not None}
    supabase.table("tasks").update(data).eq("id", task_id).execute()
    return {"status": "updated"}

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    supabase.table("tasks").delete().eq("id", task_id).execute()
    return {"status": "deleted"}

@app.delete("/projects/{project_id}")
def delete_project(project_id: int):
    supabase.table("projects").delete().eq("id", project_id).execute()
    return {"status": "deleted"}

@app.post("/leads/ingest")
def ingest_lead(req: LeadInput):
    ai_result = qualify_lead_with_ai(req.raw_input)
    extracted = ai_result.get("extracted_data", {})
    scoring = ai_result.get("scoring", {})
    data = {
        "project_id": req.project_id, 
        "name": extracted.get("name", "Unknown"), 
        "phone": extracted.get("phone", ""), 
        "email": extracted.get("email", ""), 
        "source": req.source, 
        "lead_score": scoring.get("score", 0),
        "ai_qualification": ai_result, 
        "status": "New"
    }
    res = supabase.table("leads").insert(data).execute()
    return {"status": "processed", "data": res.data[0]}

@app.get("/projects/{project_id}/leads")
def get_leads(project_id: int):
    res = supabase.table("leads").select("*").eq("project_id", project_id).order("lead_score", desc=True).execute()
    return {"leads": res.data}