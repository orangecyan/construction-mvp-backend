# templates.py

def get_wbs_template(project_type, sub_type, floors=1, towers=1):
    """
    Returns a standard WBS structure based on project parameters.
    """
    
    # 1. SINGLE FAMILY / VILLA LOGIC
    if project_type == "Residential" and sub_type in ["Villa", "Single Family"]:
        return [
            {"stage": "Pre-Construction", "desc": "Permits, Soil Testing, Site Clearing", "weather_sensitive": False},
            {"stage": "Foundation", "desc": "Excavation, Footings, Slab pouring", "weather_sensitive": True},
            {"stage": "Structure (Shell)", "desc": "Framing, Roof Trusses, Sheathing", "weather_sensitive": True},
            {"stage": "Rough MEP", "desc": "Plumbing, Electrical, HVAC ducts inside walls", "weather_sensitive": False},
            {"stage": "Insulation & Drywall", "desc": "Wall closing, Mudding, Taping", "weather_sensitive": False},
            {"stage": "Interior Finishes", "desc": "Flooring, Cabinets, Painting, Fixtures", "weather_sensitive": False},
            {"stage": "Exterior Finishes", "desc": "Siding, Stucco, Driveway, Landscaping", "weather_sensitive": True},
            {"stage": "Final Handover", "desc": "Punch list, Cleaning, Final Inspection", "weather_sensitive": False}
        ]

    # 2. HIGH-RISE / MULTI-FAMILY LOGIC
    elif project_type == "Residential" and sub_type == "High-Rise":
        # Base stages for any high rise
        wbs = [
            {"stage": "Site Mobilization", "desc": "Fencing, Cranes Setup, Site Office", "weather_sensitive": True},
            {"stage": "Excavation & Piling", "desc": "Deep excavation, Shoring, Piles", "weather_sensitive": True},
            {"stage": "Substructure (Basement)", "desc": "Basement levels, Retaining walls", "weather_sensitive": True},
            {"stage": "Podium/Lobby Level", "desc": "Ground floor high-ceilings, Transfer slabs", "weather_sensitive": True}
        ]
        
        # DYNAMIC LOGIC: Add a stage for EACH set of floors
        # We group floors to keep the WBS readable (e.g., Floors 1-5, Floors 6-10)
        floor_groups = (floors // 5) + 1
        for i in range(floor_groups):
            start = i * 5 + 1
            end = min((i + 1) * 5, floors)
            if start <= floors:
                wbs.append({
                    "stage": f"Superstructure (Floors {start}-{end})",
                    "desc": f"Column pouring, Slab casting for tower {1 if towers == 1 else 'A/B'}",
                    "weather_sensitive": True
                })

        # Add finishing stages
        wbs.extend([
            {"stage": "Facade & Envelope", "desc": "Glass curtain wall, Cladding", "weather_sensitive": True},
            {"stage": "MEP First Fix", "desc": "Risers, Main distribution lines", "weather_sensitive": False},
            {"stage": "Interiors (Fit-out)", "desc": "Partitions, Flooring, Ceilings per unit", "weather_sensitive": False},
            {"stage": "Testing & Commissioning", "desc": "Elevator testing, Fire safety systems", "weather_sensitive": False}
        ])
        return wbs

    # 3. COMMERCIAL / RETAIL LOGIC
    elif project_type == "Commercial":
        return [
            {"stage": "Site Prep", "desc": "Grading, Utilities connection", "weather_sensitive": True},
            {"stage": "Steel Structure", "desc": "Steel erection, Bolting, Decking", "weather_sensitive": True},
            {"stage": "Building Envelope", "desc": "Roofing, Exterior Walls, Glazing", "weather_sensitive": True},
            {"stage": "Core MEP", "desc": "Main HVAC units, Sprinkler mains", "weather_sensitive": False},
            {"stage": "Tenant Improvements", "desc": "Specific fit-out for retail/offices", "weather_sensitive": False}
        ]

    else:
        # Default Fallback
        return [{"stage": "General Construction", "desc": "Standard phases", "weather_sensitive": True}]