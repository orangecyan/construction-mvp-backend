def get_phase_structure(project_type):
    """
    Returns the High-Level Phases based on the Root Category.
    The AI will fill in the details inside these phases.
    """
    
    # 1. VERTICAL CONSTRUCTION (Resi, Commercial, Institutional, Mixed)
    if project_type in ["Residential", "Commercial", "Mixed-Use", "Hospitality", "Institutional", "MixedUse"]:
        return [
            "1. Pre-Construction & Permitting",
            "2. Site Work & Excavation",
            "3. Foundation & Substructure",
            "4. Superstructure (Shell)",
            "5. Building Envelope (Skin)",
            "6. MEP Rough-ins",
            "7. Interior Finishes",
            "8. Testing, Commissioning & Handover"
        ]

    # 2. INDUSTRIAL (Warehousing/Factories - Faster Shell)
    elif project_type == "Industrial":
        return [
            "1. Site Prep & Grading",
            "2. Foundation & Slab on Grade",
            "3. Steel Erection (PEB/Structural)",
            "4. Roofing & Siding",
            "5. MEP Systems",
            "6. Equipment Installation",
            "7. Final Finishes & Commissioning"
        ]

    # 3. INFRASTRUCTURE (Horizontal Build)
    elif project_type == "Infrastructure":
        return [
            "1. Survey & Utility Relocation",
            "2. Earthwork & Grading",
            "3. Structural / Civil Works",
            "4. Paving / Track / System Installation",
            "5. Signaling & Lighting",
            "6. Final Inspection"
        ]

    # 4. RENOVATION (Different Flow)
    elif project_type == "Renovation":
        return [
            "1. Assessment & Permits",
            "2. Demolition & Abatement",
            "3. Structural Alterations",
            "4. MEP Upgrades",
            "5. New Finishes",
            "6. Punch List"
        ]

    # Default Fallback
    return ["1. Mobilization", "2. Construction", "3. Closeout"]