import os
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv
from groq import Groq
from templates import get_wbs_template 

# 1. Load Environment Variables
load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# 2. Initialize Clients
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)

def save_recursive_tasks(tasks_list, stage_id, parent_id=None):
    """
    Saves tasks and their subtasks recursively.
    """
    for task in tasks_list:
        # 1. Prepare data
        task_data = {
            "stage_id": stage_id,
            "parent_task_id": parent_id, # Link to Parent
            "name": task['task_name'],
            "assigned_role": task.get('assigned_role', 'General'),
            "start_date": task.get('start_date'),
            "end_date": task.get('end_date'),
            "status": "Not Started"
        }
        
        # 2. Insert current task
        res = supabase.table("tasks").insert(task_data).execute()
        if not res.data: continue
        
        current_task_id = res.data[0]['id']

        # 3. If there are subtasks, save them inside this parent
        if 'subtasks' in task and task['subtasks']:
            save_recursive_tasks(task['subtasks'], stage_id, current_task_id)


app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Construction Backend V3", "status": "Online"}

# ---------------------------------------------------------
# DATA MODELS
# ---------------------------------------------------------

class ProjectCreate(BaseModel):
    owner_id: str 
    name: str
    code: str
    project_type: str
    sub_type: str
    address_full: str
    num_floors: int = 1
    num_units: int = 1
    plan_urls: list[str] = [] 
    start_date_planned: str
    constraints: str = "Standard construction" # Added default for AI

class JoinRequest(BaseModel):
    user_id: str 
    project_code: str

class ChatMessage(BaseModel):
    project_id: int
    user_id: str
    message: str

class ProjectRequest(BaseModel):
    # This is used for the AI Schedule Generation trigger
    name: str
    code: str
    project_type: str 
    sub_type: str     
    floors: int = 1
    towers: int = 1
    location: str     
    start_date: str   
    constraints: str  

# ---------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------

# 1. Create Project (Mega-Schema Version)
@app.post("/projects/create")
def create_project_full(req: ProjectCreate):
    # Insert Project
    data = {
        "owner_id": req.owner_id,
        "name": req.name,
        "code": req.code,
        "project_type": req.project_type,
        "sub_type": req.sub_type,
        "address_full": req.address_full,
        "num_floors": req.num_floors,
        "num_units": req.num_units,
        "plan_urls": req.plan_urls,
        "start_date_planned": req.start_date_planned,
        "status": "Planning"
    }
    
    proj_res = supabase.table("projects").insert(data).execute()
    
    if not proj_res.data:
        raise HTTPException(status_code=500, detail="Failed to create project")
    
    project_id = proj_res.data[0]['id']

    # Link Owner
    member_data = {
        "project_id": project_id,
        "user_id": req.owner_id,
        "role": "Owner",
        "member_type": "Internal",
        "permissions": {"can_edit_schedule": True, "can_chat": True, "admin": True},
        "status": "Active"
    }
    supabase.table("project_members").insert(member_data).execute()

    return {"status": "success", "project_id": project_id, "message": "Project created"}

# 2. Generate Schedule (AI Powered)
# 2. Generate Schedule (AI Powered + Recursive)
@app.post("/projects/generate-schedule")
def generate_schedule(req: ProjectRequest):
    
    # 1. Find or Create Project
    existing = supabase.table("projects").select("id").eq("code", req.code).execute()
    
    if existing.data:
        project_id = existing.data[0]['id']
    else:
        # Corrected indentation and column names here
        project_data = {
            "name": req.name,
            "project_type": req.project_type, 
            "sub_type": req.sub_type,
            "code": req.code,
            "status": "Planning"
        }
        proj_res = supabase.table("projects").insert(project_data).execute()
        project_id = proj_res.data[0]['id']

    # 2. Get Template
    base_wbs = get_wbs_template(req.project_type, req.sub_type, req.floors, req.towers)

    # 3. AI Prompt (Updated for Subtasks)
    prompt = f"""
    Act as a Senior Construction Scheduler.
    Project: {req.sub_type} in {req.location}.
    Start Date: {req.start_date}.
    Floors: {req.floors}.
    Constraints: {req.constraints}.

    Here is the Standard WBS Stages: {json.dumps(base_wbs)}

    Task:
    1. Break down each stage into Main Tasks.
    2. Break down complex Main Tasks into SUB-TASKS (Micro-details).
    3. Assign Roles and Dates.

    Return ONLY valid JSON in this format:
    {{
        "schedule": [
            {{
                "stage_name": "Stage Name",
                "start_date": "YYYY-MM-DD",
                "end_date": "YYYY-MM-DD",
                "tasks": [
                    {{
                        "task_name": "Main Task",
                        "assigned_role": "Trade Name", 
                        "start_date": "YYYY-MM-DD", 
                        "end_date": "YYYY-MM-DD",
                        "subtasks": [
                            {{ "task_name": "Micro-Task 1", "assigned_role": "Helper" }}
                        ]
                    }}
                ]
            }}
        ]
    }}
    """

    # 4. Call AI
    chat_completion = groq_client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
        response_format={"type": "json_object"}
    )

    schedule_data = json.loads(chat_completion.choices[0].message.content)

    # 5. Save to Database (Using the Helper Function)
    for item in schedule_data['schedule']:
        # Save Stage
        stage_data = {
            "project_id": project_id,
            "name": item['stage_name'],
            "status": "Scheduled",
            "start_date": item['start_date'],
            "end_date": item['end_date']
        }
        stage_res = supabase.table("stages").insert(stage_data).execute()
        
        if not stage_res.data: continue
        new_stage_id = stage_res.data[0]['id']

        # Save Tasks Recursive
        if 'tasks' in item:
            save_recursive_tasks(item['tasks'], new_stage_id, parent_id=None)

    return {"status": "success", "project_id": project_id, "ai_schedule": schedule_data}

# 3. Join Project
@app.post("/projects/join")
def join_project(req: JoinRequest):
    project = supabase.table("projects").select("id").eq("code", req.project_code).execute()
    
    if not project.data:
        raise HTTPException(status_code=404, detail="Invalid Project Code")
    
    project_id = project.data[0]['id']

    # Check if member
    existing = supabase.table("project_members").select("*").eq("user_id", req.user_id).eq("project_id", project_id).execute()
    if existing.data:
        return {"message": "Already a member"}

    # Add Member
    member_data = {
        "project_id": project_id,
        "user_id": req.user_id,
        "role": "Subcontractor",
        "member_type": "External",
        "permissions": {"can_chat": True, "can_edit_schedule": False},
        "status": "Active"
    }
    supabase.table("project_members").insert(member_data).execute()
    
    return {"status": "joined", "project_id": project_id}

# 4. Smart Chat
@app.post("/chat/send")
def send_chat_update(req: ChatMessage):
    # Log Chat
    supabase.table("chat_logs").insert({
        "project_id": req.project_id,
        "user_id": req.user_id,
        "message_text": req.message
    }).execute()

    # Context for AI
    tasks_res = supabase.table("tasks").select("id, name, status").eq("status", "Not Started").limit(20).execute()
    tasks_context = json.dumps(tasks_res.data)

    prompt = f"""
    Construction Manager AI. 
    Current Tasks: {tasks_context}
    Worker Update: "{req.message}"
    
    Return JSON: {{ "matched_task_id": 123 (or null), "new_status": "Completed", "completion": 100 }}
    """

    chat_completion = groq_client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
        response_format={"type": "json_object"}
    )
    
    ai_analysis = json.loads(chat_completion.choices[0].message.content)

    if ai_analysis.get("matched_task_id"):
        task_id = ai_analysis["matched_task_id"]
        new_status = ai_analysis["new_status"]
        supabase.table("tasks").update({"status": new_status}).eq("id", task_id).execute()
        return {"status": "Updated", "ai_action": f"Task {task_id} -> {new_status}"}

    return {"status": "Sent", "ai_action": "No changes"}

# 5. Get Dashboard Data
@app.get("/projects/{project_id}/dashboard")
def get_project_dashboard(project_id: int):
    proj = supabase.table("projects").select("*").eq("id", project_id).execute()
    
    data = supabase.table("stages")\
        .select("id, name, start_date, end_date, status, tasks(id, name, assigned_role, start_date, end_date, status)")\
        .eq("project_id", project_id)\
        .order("start_date")\
        .execute()
        
    if not data.data:
        return {"message": "No data found"}

    return {"project": proj.data[0], "timeline_data": data.data}