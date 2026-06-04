# Security & Governance: RBAC and ABAC Configuration

# Define corporate user profiles with roles, department attributes, and security clearances.
USER_DIRECTORY = {
    "Sarah Jenkins (HR Manager)": {
        "user_id": "sjenkins@company.com",
        "role": "HR_Manager",
        "allowed_departments": ["HR", "Operations"],
        "clearance_level": "Confidential",
        "description": "Access to Human Resource policies, personnel files, and general operations documents."
    },
    "David Miller (Finance Analyst)": {
        "user_id": "dmiller@company.com",
        "role": "Finance_Analyst",
        "allowed_departments": ["Finance", "Operations"],
        "clearance_level": "Confidential",
        "description": "Access to Q1 performance statements, budget ledgers, and general operations guidelines."
    },
    "Alex Carter (IT Admin)": {
        "user_id": "acarter@company.com",
        "role": "IT_Administrator",
        "allowed_departments": ["IT", "Operations"],
        "clearance_level": "Confidential",
        "description": "Access to standard operating procedures, network incident plans, and general operations guidelines."
    },
    "Elena Rostova (Executive VP)": {
        "user_id": "erostova@company.com",
        "role": "Executive_VP",
        "allowed_departments": ["HR", "Finance", "IT", "Operations"],
        "clearance_level": "Secret",
        "description": "Executive level access across all corporate departments, including sensitive/secret documentation."
    },
    "John Doe (General Contractor)": {
        "user_id": "jdoe@company.com",
        "role": "Guest_Employee",
        "allowed_departments": ["Operations"],
        "clearance_level": "Public",
        "description": "General guest access. Restrictive access to standard public/general operations documents only."
    }
}

# Mapping of security levels to numeric hierarchy (for clearance checks)
CLEARANCE_HIERARCHY = {
    "Public": 1,
    "Confidential": 2,
    "Secret": 3
}

def get_user_profiles():
    """Return all mock user profiles."""
    return USER_DIRECTORY

def get_user_profile(user_key):
    """Retrieve details for a specific user name."""
    return USER_DIRECTORY.get(user_key)

def evaluate_abac_policy(user_profile, doc_department, doc_clearance_level):
    """
    Evaluates ABAC (Attribute-Based Access Control) policy.
    Checks if a user has authorization to access a document based on department and clearance hierarchy.
    """
    if not user_profile:
        return False, "User profile not found."

    # 1. Department Attribute Alignment Check
    user_depts = user_profile.get("allowed_departments", [])
    if doc_department not in user_depts:
        return False, f"Department access violation: User is in {user_depts}, document belongs to {doc_department}."

    # 2. Clearance Level Check (Hierarchy-based)
    user_clearance = user_profile.get("clearance_level", "Public")
    user_level_score = CLEARANCE_HIERARCHY.get(user_clearance, 1)
    doc_level_score = CLEARANCE_HIERARCHY.get(doc_clearance_level, 1)

    if user_level_score < doc_level_score:
        return False, f"Clearance level violation: User clearance '{user_clearance}' is lower than document clearance '{doc_clearance_level}'."

    return True, "Access Granted"
