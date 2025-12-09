import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv

# 1. Load the keys from .env file
load_dotenv()

# 2. Initialize Supabase
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

app = FastAPI()

# 3. Define the Data Model (What data do we expect from the frontend?)
class ProjectCreate(BaseModel):
    name: str
    type: str
    code: str

@app.get("/")
def read_root():
    return {"message": "Construction Backend V2", "db_status": "Connected"}

# 4. The "Create Project" Endpoint
@app.post("/projects/")
def create_project(project: ProjectCreate):
    # Prepare data for Supabase
    data = {
        "name": project.name,
        "type": project.type,
        "code": project.code
    }
    
    # Insert into database
    response = supabase.table("projects").insert(data).execute()
    
    # Check if successful
    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to create project")
        
    return {"message": "Project created successfully", "data": response.data}