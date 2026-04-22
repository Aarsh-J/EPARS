"""
config.py — Shared constants for all V3 dataset generation scripts.
All scripts import from here. Edit master row counts in 00_master.py.
"""

# ─── Departments & Roles ───────────────────────────────────────────────────────
DEPARTMENTS = ["Engineering", "Sales", "Marketing", "HR", "Finance", "Design", "Operations"]

DEPT_ROLES = {
    "Engineering":  ["Software Engineer", "Senior Engineer", "Team Lead", "Developer", "Principal Engineer"],
    "Sales":        ["Sales Representative", "Account Manager", "Sales Manager", "Business Developer"],
    "Marketing":    ["Marketing Analyst", "Content Strategist", "Marketing Manager", "SEO Specialist"],
    "HR":           ["HR Analyst", "HR Manager", "Recruiter", "L&D Specialist"],
    "Finance":      ["Financial Analyst", "Accountant", "Finance Manager", "Controller"],
    "Design":       ["UI/UX Designer", "Graphic Designer", "Design Lead", "Product Designer"],
    "Operations":   ["Operations Analyst", "Project Coordinator", "Operations Manager", "Scrum Master"],
}

# ─── Seniority ────────────────────────────────────────────────────────────────
SENIORITY_LEVELS  = ["Junior", "Mid", "Senior", "Lead", "Principal"]
SENIORITY_WEIGHTS = [0.25, 0.30, 0.25, 0.15, 0.05]
SENIOR_LEVELS     = {"Senior", "Lead", "Principal"}

SENIORITY_EXP_RANGE = {
    "Junior":    (0.5, 2.5),
    "Mid":       (2.5, 6.0),
    "Senior":    (6.0, 12.0),
    "Lead":      (8.0, 18.0),
    "Principal": (12.0, 25.0),
}

# Base salary range by seniority (adjusted by dept multiplier below)
SENIORITY_SAL_RANGE = {
    "Junior":    (40_000,  65_000),
    "Mid":       (60_000,  90_000),
    "Senior":    (85_000, 130_000),
    "Lead":      (110_000, 160_000),
    "Principal": (140_000, 200_000),
}

# Department salary multiplier applied on top of seniority range
DEPT_SAL_MULTIPLIER = {
    "Engineering": 1.20,
    "Finance":     1.10,
    "Sales":       1.05,
    "Marketing":   0.95,
    "Design":      1.00,
    "Operations":  0.95,
    "HR":          0.90,
}

SENIORITY_BOOST = {
    "Junior": 0.0, "Mid": 0.1, "Senior": 0.2, "Lead": 0.25, "Principal": 0.3
}

# Seniority → numeric order (used for experience_match_score)
SENIORITY_ORDER = {"Junior": 1, "Mid": 2, "Senior": 3, "Lead": 4, "Principal": 5}

# Base scores for derived calculations
SENIORITY_TECH_BASE  = {"Junior": 35, "Mid": 52, "Senior": 68, "Lead": 80, "Principal": 90}
SENIORITY_DOMAIN_BASE= {"Junior": 25, "Mid": 45, "Senior": 62, "Lead": 78, "Principal": 90}
SENIORITY_LP_BASE    = {"Junior": 20, "Mid": 38, "Senior": 58, "Lead": 75, "Principal": 88}

# ─── Skills — Single Source of Truth ──────────────────────────────────────────
DEPT_SKILLS = {
    "Engineering": (
        ["Python", "Java", "Go", "C++", "React", "Node.js", "AWS", "Docker",
         "Kubernetes", "SQL", "TypeScript", "Rust"],
        ["Git", "Linux", "Agile", "REST APIs", "Microservices"],
    ),
    "Sales": (
        ["CRM", "Salesforce", "Negotiation", "Lead Generation", "B2B Sales"],
        ["Excel", "PowerPoint", "Communication", "Networking"],
    ),
    "Marketing": (
        ["Google Analytics", "SEO", "Content Marketing", "Social Media", "HubSpot", "Copywriting"],
        ["Canva", "Excel", "Analytics", "Email Marketing"],
    ),
    "HR": (
        ["Recruitment", "HRIS", "Performance Management", "Employee Relations", "Training"],
        ["Excel", "Communication", "Conflict Resolution", "Onboarding"],
    ),
    "Finance": (
        ["Financial Modeling", "Excel", "SAP", "Accounting", "Budgeting", "Forecasting"],
        ["SQL", "PowerBI", "Tableau", "Communication"],
    ),
    "Design": (
        ["Figma", "Adobe XD", "Sketch", "Photoshop", "Illustrator", "UI/UX", "Prototyping"],
        ["CSS", "HTML", "User Research", "Wireframing"],
    ),
    "Operations": (
        ["Project Management", "Jira", "Process Improvement", "Supply Chain", "Lean", "Six Sigma"],
        ["Excel", "Agile", "Communication", "Risk Management"],
    ),
}

ALL_SKILLS = sorted({s for pri, sec in DEPT_SKILLS.values() for s in pri + sec})

CERTS_BY_DEPT = {
    "Engineering":  ["AWS Certified", "GCP Professional", "Azure Certified", "Kubernetes CKA", "Scrum Master"],
    "Sales":        ["Salesforce Certified", "HubSpot Certified", "Sales Bootcamp"],
    "Marketing":    ["Google Analytics", "Google Ads", "HubSpot Marketing", "Facebook Blueprint"],
    "HR":           ["SHRM-CP", "PHR", "CIPD", "Talent Management"],
    "Finance":      ["CPA", "CFA", "FRM", "CMA", "ACCA"],
    "Design":       ["Google UX Design", "Figma Certified", "Adobe Certified"],
    "Operations":   ["PMP", "Scrum Master", "Six Sigma Green Belt", "ITIL"],
}

SKILLS_BY_TASK_TYPE = {
    "Development":   ["Python", "Java", "Go", "React", "Node.js", "SQL", "TypeScript", "C++", "REST APIs", "Docker"],
    "Design":        ["Figma", "Adobe XD", "UI/UX", "Prototyping", "Sketch", "Illustrator", "CSS", "HTML"],
    "Testing":       ["Python", "SQL", "Docker", "REST APIs", "Git"],
    "Research":      ["SQL", "Excel", "Python", "Analytics", "Communication"],
    "Documentation": ["Communication", "Git", "Agile", "Excel"],
    "Meeting":       ["Communication", "Agile"],
    "DevOps":        ["Docker", "Kubernetes", "AWS", "Linux", "Git"],
    "Review":        ["Git", "Python", "Java", "React", "Agile"],
}

# ─── Employment ───────────────────────────────────────────────────────────────
EMP_TYPES         = ["Full-time", "Part-time", "Contract"]
EMP_TYPE_WEIGHTS  = [0.80, 0.10, 0.10]
EMP_TYPE_CAPACITY = {"Full-time": 40, "Part-time": 20, "Contract": 30}
EMP_TYPE_BILLABLE = {"Full-time": 0.80, "Part-time": 0.70, "Contract": 0.90}

# ─── Employee misc lookups ────────────────────────────────────────────────────
REMOTE_STATUS  = ["Remote", "Hybrid", "Office"]
WORK_HOURS     = ["9am-5pm", "10am-6pm", "8am-4pm", "Flexible"]
TEAM_SIZE_PREF = ["Small (2-4)", "Medium (5-8)", "Large (9+)"]
PROD_TREND     = ["Increasing", "Stable", "Decreasing"]
PROD_TREND_W   = [0.30, 0.50, 0.20]
STRESS_LEVELS  = ["Low", "Medium", "High"]

FIRST_NAMES = [
    "Aarna","Aarsh","Advaith","Ahana","Arjun","Priya","Rohan","Sneha","Vikram","Meera",
    "Kiran","Divya","Rajan","Ananya","Siddharth","Pooja","Neel","Isha","Rahul","Kavya",
    "John","Sarah","Michael","Emily","David","Jessica","Chris","Ashley","Daniel","Amanda",
    "James","Jennifer","Robert","Lisa","William","Karen","Richard","Nancy","Thomas","Betty",
    "Carlos","Maria","Jose","Ana","Miguel","Carmen","Luis","Rosa","Jorge","Isabel",
    "Raj","Priti","Amit","Sunita","Nikhil","Swati","Gaurav","Deepa","Vishal","Rekha",
    "Lena","Hans","Anna","Klaus","Ingrid","Erik","Astrid","Lars","Freya","Magnus",
    "Wei","Li","Fang","Jun","Mei","Hao","Xiu","Ping","Jing","Yang",
    "Alex","Jordan","Taylor","Morgan","Casey","Riley","Jamie","Avery","Quinn","Reese",
]
LAST_NAMES = [
    "Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Martinez","Wilson",
    "Kumar","Sharma","Patel","Singh","Nair","Menon","Iyer","Reddy","Gupta","Shah",
    "Anderson","Taylor","Thomas","Jackson","White","Harris","Martin","Thompson","Young","Lewis",
    "Walker","Hall","Allen","Wright","Scott","Torres","Nguyen","Hill","Flores","Green",
    "Jain","Nambiar","Acharya","Bose","Chatterjee","Das","Ghosh","Mukherjee","Roy","Sen",
    "Muller","Schmidt","Fischer","Weber","Meyer","Wagner","Becker","Hoffman","Koch","Bauer",
    "Chen","Wang","Zhang","Liu","Yang","Huang","Zhao","Wu","Zhou","Sun",
]

# ─── Project lookups ──────────────────────────────────────────────────────────
PROJECT_TYPES = ["Product Development", "Marketing", "Internal", "Research", "Client Project"]
PROJ_STATUS   = ["Planning", "Active", "On Hold", "Completed", "Cancelled"]
PROJ_STATUS_W = [0.08, 0.25, 0.07, 0.55, 0.05]
COMPLEXITY    = ["Low", "Medium", "High", "Very High"]
PRIORITY      = ["Low", "Medium", "High", "Critical"]
PRIORITY_W    = [0.10, 0.35, 0.35, 0.20]

COMPLEXITY_BUDGET   = {"Low": (20_000, 80_000), "Medium": (80_000, 300_000),
                       "High": (300_000, 800_000), "Very High": (800_000, 2_000_000)}
COMPLEXITY_DURATION = {"Low": 30, "Medium": 90, "High": 180, "Very High": 270}
COMPLEXITY_RISK_BASE= {"Low": 12, "Medium": 28, "High": 50, "Very High": 68}

PROJECT_NAMES = [
    "Mobile App Redesign","Customer Portal Upgrade","Data Warehouse Migration",
    "AI Chatbot Integration","Sales Automation Pipeline","HR Self-Service Portal",
    "Security Compliance Audit","Cloud Infrastructure Overhaul",
    "Marketing Analytics Dashboard","Employee Onboarding System",
    "Real-Time Monitoring Platform","API Gateway Modernization",
    "Recommendation Engine","Fraud Detection System","Supply Chain Optimizer",
    "Digital Twin Prototype","Q1 Marketing Campaign","Brand Refresh Initiative",
    "SEO Content Strategy","Lead Generation Funnel","Financial Reporting Automation",
    "Budget Forecasting Tool","Expense Management System","Payroll Integration",
    "Design System Library","User Research Study","Accessibility Compliance Project",
    "Prototype Testing Sprint","Process Automation Initiative","Vendor Management Portal",
    "Capacity Planning Tool","Incident Response Framework","Performance Review Overhaul",
    "Learning Management System","Internal Knowledge Base","Code Quality Initiative",
    "DevOps Transformation","Microservices Migration","Data Privacy Compliance",
    "Customer Feedback Platform",
]

# ─── Task lookups ─────────────────────────────────────────────────────────────
TASK_TYPES       = ["Development", "Design", "Testing", "Research", "Documentation",
                    "Meeting", "DevOps", "Review"]
TASK_COMPLEXITY  = ["Simple", "Moderate", "Complex", "Very Complex"]
TASK_COMPLEXITY_W= [0.20, 0.35, 0.30, 0.15]
RISK_LEVEL       = ["Low", "Medium", "High"]
BIZ_IMPACT       = ["Low", "Medium", "High", "Critical"]

COMPLEXITY_EST_HOURS = {"Simple": (1, 8), "Moderate": (8, 24), "Complex": (24, 80), "Very Complex": (80, 200)}
COMPLEXITY_STORY_PTS = {"Simple": [1, 2, 3], "Moderate": [3, 5, 8], "Complex": [8, 13], "Very Complex": [13, 21]}

ROLE_BY_TASK_TYPE = {
    "Development":   "Developer",
    "Design":        "Designer",
    "Testing":       "Developer",
    "Research":      "Analyst",
    "Documentation": "Developer",
    "Meeting":       "Manager",
    "DevOps":        "Developer",
    "Review":        "Senior Engineer",
}

TASK_NAMES_BY_TYPE = {
    "Development":   ["Implement user authentication", "Build REST API endpoint",
                      "Develop payment gateway", "Create database schema",
                      "Refactor legacy module", "Build notification service",
                      "Implement caching layer", "Develop admin dashboard",
                      "Create data pipeline", "Build search feature"],
    "Design":        ["Design landing page", "Create wireframes", "Build design system",
                      "Design onboarding flow", "Create icon set", "Design email templates",
                      "Prototype user journey", "Redesign settings page"],
    "Testing":       ["Write unit tests", "Perform integration testing", "Conduct load testing",
                      "Run regression suite", "Security vulnerability scan",
                      "Accessibility audit", "API contract testing", "E2E test automation"],
    "Research":      ["Evaluate third-party libraries", "Conduct user research",
                      "Benchmark database options", "Research ML frameworks",
                      "Competitive analysis", "Technology feasibility study"],
    "Documentation": ["Write API documentation", "Update onboarding guide", "Create runbook",
                      "Document architecture", "Write release notes", "Update README"],
    "Meeting":       ["Sprint planning", "Retrospective", "Stakeholder review",
                      "Design critique", "Architecture discussion", "Team sync"],
    "DevOps":        ["Setup CI/CD pipeline", "Configure monitoring", "Deploy to staging",
                      "Optimize Docker images", "Setup alerting rules",
                      "Database backup automation", "Infrastructure as code"],
    "Review":        ["Code review", "Design review", "Architecture review",
                      "PR review", "Document review"],
}

TASK_STATUS = ["Not Started", "In Progress", "In Review", "Completed", "Blocked"]

# ─── Schedule lookups ─────────────────────────────────────────────────────────
HISTORY_START  = "2024-01-01"
HISTORY_END    = "2025-02-28"

EVENT_TYPES    = ["Task", "Meeting", "Focus Time", "Break", "Training", "Leave"]
EVENT_WEIGHTS  = [0.30, 0.30, 0.20, 0.08, 0.07, 0.05]
MTG_TYPES      = ["One-on-One", "Team Meeting", "All-Hands", "Training", "Standup"]
ATTEND_STATUS  = ["Scheduled", "Completed", "Missed", "Rescheduled", "Cancelled"]
ATTEND_WEIGHTS = [0.15, 0.60, 0.08, 0.10, 0.07]
WORK_LOCATIONS = ["Office", "Home", "Remote", "Client Site"]
SPECIAL_CIRC   = ["Holiday", "Training Day", "Client Visit", "Team Offsite", None, None, None, None]

DURATION_BY_TYPE = {
    "Task":       [60, 90, 120, 180, 240],
    "Meeting":    [30, 45, 60, 90],
    "Focus Time": [60, 90, 120],
    "Break":      [15, 30, 60],
    "Training":   [60, 120, 180, 240],
    "Leave":      [480],
}

EVENT_TITLES = {
    "Task":       ["Code Review Session", "Implementation Block", "Design Sprint",
                   "Bug Fixing", "Testing Block"],
    "Meeting":    ["Sprint Planning", "Daily Standup", "Retrospective",
                   "Stakeholder Review", "1:1 with Manager", "Design Critique",
                   "Architecture Discussion", "Team Sync", "All Hands"],
    "Focus Time": ["Deep Work Block", "No-Interruption Zone", "Research Block",
                   "Writing Time", "Strategy Session"],
    "Break":      ["Lunch Break", "Coffee Break", "Short Walk", "Mental Reset"],
    "Training":   ["AWS Training", "Leadership Workshop", "Agile Certification Prep",
                   "Technical Talk", "Onboarding"],
    "Leave":      ["Annual Leave", "Sick Leave", "Personal Day", "Public Holiday"],
}

# ─── Burnout lookups ──────────────────────────────────────────────────────────
BURNOUT_TREND  = ["Decreasing", "Stable", "Increasing", "Rapidly Increasing"]
INTERV_URGENCY = ["None", "Monitor", "Recommend", "Immediate"]
ASSESS_TYPE    = ["Daily", "Weekly", "Monthly", "On-Demand"]
ASSESS_WEIGHTS = [0.10, 0.50, 0.30, 0.10]

# ─── Team formation lookups ───────────────────────────────────────────────────
FORMATION_METHOD  = ["Manual", "AI-Recommended", "Hybrid"]
FORMATION_WEIGHTS = [0.35, 0.40, 0.25]
TEAM_STATUS       = ["Active", "Completed", "Disbanded", "On Hold"]
TEAM_STATUS_W     = [0.30, 0.45, 0.15, 0.10]

TEAM_NAMES = [
    "Alpha Squad","Beta Crew","Delta Force","Gamma Team","Omega Unit",
    "Phoenix Team","Nexus Crew","Titan Squad","Vortex Team","Apex Unit",
    "Backend Crew","Frontend Force","Data Squad","Design Dream Team",
    "DevOps Warriors","QA Guardians","Platform Team","Growth Squad",
    "Research Collective","Strategy Unit","Innovation Lab","Core Team",
    "Velocity Squad","Agile Avengers","Sprint Masters","Cloud Ninjas",
    "Security Squad","AI Task Force","Analytics Crew","Mobile Team",
]

# ─── Performance review lookups ───────────────────────────────────────────────
REVIEW_TYPES    = ["Annual", "Quarterly", "Project-based", "Probationary"]
REVIEW_WEIGHTS  = [0.40, 0.35, 0.15, 0.10]
PROMO_READINESS = ["Not Ready", "Ready in 6-12 months", "Ready Now"]
PERF_RATING_BANDS = [
    (0,   60,  "Needs Improvement"),
    (60,  75,  "Meets Expectations"),
    (75,  88,  "Exceeds Expectations"),
    (88, 101,  "Outstanding"),
]

STRENGTHS_POOL = [
    "Technical expertise","Problem solving","Communication","Leadership",
    "Collaboration","Time management","Innovation","Mentoring",
    "Attention to detail","Adaptability","Reliability","Initiative",
]
WEAKNESS_POOL = [
    "Documentation","Public speaking","Time estimation","Delegation",
    "Conflict resolution","Strategic thinking","Cross-team communication",
    "Process adherence","Work-life balance","Stakeholder management",
]
TRAINING_POOL = [
    "Leadership Training","AWS Certification","Agile Course","Communication Workshop",
    "Data Analysis Bootcamp","PMP Certification","Scrum Master Training",
    "Technical Writing","Python Advanced","Cloud Architecture",
]
MANAGER_COMMENTS = [
    "Strong performer who consistently delivers high-quality work.",
    "Shows great initiative and is a reliable team member.",
    "Has significant potential for growth with focused development.",
    "Excellent collaborator who elevates the entire team.",
    "Demonstrates strong technical skills with room for soft-skill growth.",
    "A dependable contributor who meets expectations consistently.",
    "Outstanding performance this period — exceeds on all fronts.",
    "Needs to focus on delivery timelines and communication.",
]
PEER_FEEDBACK = [
    "Great collaborator, always willing to help the team.",
    "Brings strong expertise and shares knowledge freely.",
    "Reliable and communicates blockers early.",
    "Could improve on proactively sharing updates.",
    "A pleasure to work with — highly recommended for future teams.",
    "Strong technical contributor, great pair-programming partner.",
]
ACHIEVEMENTS_POOL = [
    "Led successful product launch ahead of schedule",
    "Mentored 2 junior team members",
    "Reduced system latency by 40%",
    "Delivered critical feature with zero post-release bugs",
    "Improved test coverage from 45% to 82%",
    "Automated deployment pipeline saving 5hrs/week",
    "Won internal hackathon with innovative prototype",
    "Resolved major production incident within SLA",
]

# ─── Feedback lookups ─────────────────────────────────────────────────────────
FB_TYPES    = ["Task Completion", "Project Review", "Peer Feedback", "Self Assessment"]
FB_TYPES_W  = [0.35, 0.25, 0.30, 0.10]
FB_CATEGORY = ["Technical Skills", "Communication", "Leadership", "Quality", "Teamwork"]
VISIBILITY  = ["Private", "Team", "Manager Only", "Public"]
VISIBILITY_W= [0.25, 0.30, 0.30, 0.15]

POSITIVE_ASPECTS_POOL = [
    "Clear communication","On-time delivery","High quality output",
    "Proactive problem solving","Strong collaboration","Attention to detail",
    "Technical depth","Team support","Initiative shown","Reliable execution",
]
IMPROVE_AREAS_POOL = [
    "Documentation quality","Testing coverage","Time estimation accuracy",
    "Stakeholder updates","Code readability","Proactive communication",
    "Deadline adherence","Cross-team alignment","Technical depth","Process adherence",
]
SUGGESTIONS_POOL = [
    "Consider adding more unit tests to improve coverage",
    "Document API endpoints before handoff",
    "Schedule earlier check-ins with stakeholders",
    "Break large tasks into smaller trackable subtasks",
    "Improve commit message quality for better traceability",
    "Conduct a brief knowledge-sharing session with the team",
    "Request early feedback instead of waiting until delivery",
    None,
]
FB_TEXT_POOL = [
    "Delivered the task with great attention to detail and minimal rework needed.",
    "Strong collaboration throughout the sprint, kept the team unblocked.",
    "Quality of deliverables was high, stakeholders were satisfied.",
    "Communication was proactive and clear during the entire project phase.",
    "Technical execution was excellent but documentation was lacking.",
    "Showed great initiative in identifying and resolving blockers early.",
    "Met all deadlines and maintained consistent quality standards.",
    "Good work overall, with some areas to improve in cross-team coordination.",
    "Exceeded expectations on the technical front, peer feedback is very positive.",
    "Delivery was slightly delayed but final output quality was strong.",
]
ACTION_ITEMS_POOL = [
    "Complete training,Review documentation",
    "Improve test coverage,Update runbook",
    "Schedule 1:1 with manager,Review goals",
    "Enroll in leadership course,Improve delegation",
    "Attend communication workshop",
    None,
]
RECIPIENT_RESPONSES = [
    "Thank you for the feedback, will work on documentation.",
    "Appreciate the recognition, will continue improving.",
    "Acknowledged — will focus on the suggested areas.",
    "Feedback received and noted, will discuss with manager.",
    None, None,
]

# ─── Shared helpers ───────────────────────────────────────────────────────────
import random
import numpy as np
from datetime import date, timedelta


def clamp(val, lo, hi):
    return max(lo, min(hi, val))


def rand_date(start: date, end: date) -> date:
    if start >= end:
        return start
    return start + timedelta(days=random.randint(0, (end - start).days))


def rand_datetime(d_start, d_end=None, h_lo=8, h_hi=18) -> str:
    if d_end is not None:
        d = rand_date(d_start, d_end)
    else:
        d = d_start
    h = random.randint(h_lo, h_hi)
    m = random.choice([0, 15, 30, 45])
    return f"{d} {h:02d}:{m:02d}:00"


def pick(lst, k=1, sep=","):
    k = max(1, k)
    sample = random.sample(lst, min(k, len(lst)))
    return sep.join(sample) if len(sample) > 1 else sample[0]


def normal_score(mu, sigma, lo=1.0, hi=10.0):
    return clamp(round(np.random.normal(mu, sigma), 1), lo, hi)


def normal_pct(mu, sigma, lo=0.0, hi=100.0):
    return clamp(round(np.random.normal(mu, sigma), 1), lo, hi)


def perf_rating_from_score(score: float) -> str:
    for lo, hi, label in PERF_RATING_BANDS:
        if lo <= score < hi:
            return label
    return "Meets Expectations"


def get_emp_skills(emp_row) -> set:
    """Return full skill set for an employee (primary + secondary)."""
    skills = set()
    for col in ["primary_skills", "secondary_skills"]:
        val = emp_row.get(col, "")
        if val and str(val).lower() not in ("none", "nan", ""):
            skills.update(s.strip() for s in str(val).split(","))
    return skills


def add_minutes(time_str: str, minutes: int) -> str:
    """Add minutes to HH:MM:SS, capping at 23:59:00."""
    h, m, s = map(int, time_str.split(":"))
    total = h * 60 + m + minutes
    total = min(total, 23 * 60 + 59)
    return f"{total // 60:02d}:{total % 60:02d}:00"


def weekdays_in_range(start: date, end: date) -> list:
    days, cur = [], start
    while cur <= end:
        if cur.weekday() < 5:
            days.append(cur)
        cur += timedelta(days=1)
    return days
