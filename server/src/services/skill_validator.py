"""
Validates skills entered by candidates.
- Checks against a known skills list (case-insensitive).
- Suggests corrections for likely typos (edit distance ≤ 2).
- Flags completely unrecognised tokens so the UI can prompt the user.
"""

# ── Known skills ──────────────────────────────────────────────────────────────

KNOWN_SKILLS: set[str] = {
    # Languages
    "python","javascript","typescript","java","c++","c#","go","rust","php","ruby",
    "swift","kotlin","r","scala","perl","dart","elixir","haskell","lua","bash",
    "powershell","sql","html","css","sass","less","matlab","groovy","clojure",
    # Web frameworks / libraries
    "react","vue","angular","next.js","nuxt.js","svelte","jquery","express",
    "django","flask","fastapi","laravel","rails","spring","asp.net","gatsby",
    "remix","htmx","nestjs","graphql","rest api","restful","websocket",
    # Mobile
    "react native","flutter","ios","android","xamarin","ionic","expo",
    # Databases
    "postgresql","mysql","mongodb","redis","sqlite","dynamodb","cassandra",
    "oracle","sql server","elasticsearch","firebase","supabase","mariadb",
    "couchdb","neo4j","influxdb","snowflake","bigquery",
    # Cloud & DevOps
    "aws","azure","gcp","google cloud","docker","kubernetes","terraform",
    "ansible","jenkins","github actions","gitlab ci","ci/cd","linux","nginx",
    "apache","heroku","vercel","netlify","cloudflare","serverless",
    # Data & AI
    "machine learning","deep learning","tensorflow","pytorch","pandas","numpy",
    "scikit-learn","data science","nlp","computer vision","data analysis",
    "tableau","power bi","hadoop","spark","airflow","keras","xgboost","opencv",
    "langchain","llm","rag","data engineering","etl","dbt",
    # Design
    "figma","adobe xd","sketch","photoshop","illustrator","indesign",
    "ui design","ux design","ui/ux","wireframing","prototyping","user research",
    "motion design","3d modeling","blender","cinema 4d",
    # Project management / soft skills
    "project management","agile","scrum","kanban","jira","confluence",
    "product management","business analysis","stakeholder management",
    # Marketing / content
    "digital marketing","seo","sem","content writing","copywriting","social media",
    "email marketing","google analytics","hubspot","salesforce",
    # Finance
    "accounting","bookkeeping","financial analysis","auditing","tax preparation",
    "financial modeling","excel","quickbooks","sap","erp",
    # Medical
    "surgery","cardiology","pediatrics","psychiatry","nursing","dentistry",
    "pharmacy","radiology","oncology","orthopedics","general medicine",
    "anatomy","physiology","clinical research","patient care","icu",
    # Legal
    "contract law","corporate law","criminal law","intellectual property",
    "litigation","legal research","compliance","gdpr","due diligence",
    # Education
    "curriculum development","lesson planning","e-learning","tutoring",
    "classroom management","instructional design","lms",
    # Engineering (non-software)
    "civil engineering","mechanical engineering","electrical engineering",
    "structural engineering","autocad","solidworks","catia","matlab",
    # Media / creative
    "photography","video editing","adobe premiere","final cut pro",
    "after effects","unity","unreal engine","game development",
    # Security
    "cybersecurity","penetration testing","network security","ethical hacking",
    "soc","siem","owasp","ssl/tls","vpn",
    # Blockchain
    "blockchain","web3","solidity","smart contracts","defi","nft",
    # Other
    "communication","leadership","teamwork","problem solving","time management",
    "research","data visualization","microsoft office","word","excel","powerpoint",
}

# Lowercase lookup for fast membership test
_SKILLS_LOWER: set[str] = {s.lower() for s in KNOWN_SKILLS}


# ── Levenshtein distance (no dependencies) ────────────────────────────────────

def _edit_distance(a: str, b: str) -> int:
    if abs(len(a) - len(b)) > 3:
        return 99  # Fast reject
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = temp
    return dp[n]


def _suggest(skill_lower: str) -> str | None:
    """Return the closest known skill if edit distance ≤ 2, else None."""
    best, best_d = None, 3
    for known in _SKILLS_LOWER:
        d = _edit_distance(skill_lower, known)
        if d < best_d:
            best, best_d = known, d
    return best


# ── Public API ────────────────────────────────────────────────────────────────

def validate_skills(skills: list[str]) -> dict:
    """
    Returns:
      valid:       list of recognised skills (as entered)
      unrecognised: list of skills not in the known list
      suggestions: {original: suggestion} — only when a close match exists
    """
    valid, unrecognised, suggestions = [], [], {}
    for skill in skills:
        lower = skill.lower().strip()
        if lower in _SKILLS_LOWER:
            valid.append(skill)
        else:
            suggestion = _suggest(lower)
            unrecognised.append(skill)
            if suggestion:
                suggestions[skill] = suggestion
    return {"valid": valid, "unrecognised": unrecognised, "suggestions": suggestions}


# ── Skill → domain mapping (for title consistency check) ─────────────────────

_TECH_SKILLS = {
    "python","javascript","typescript","java","c++","c#","go","rust","php","ruby",
    "swift","kotlin","react","vue","angular","next.js","django","flask","fastapi",
    "node","express","spring","sql","postgresql","mysql","mongodb","redis","docker",
    "kubernetes","aws","azure","gcp","machine learning","deep learning","data science",
    "tensorflow","pytorch","pandas","numpy","ai","llm","blockchain","web3","solidity",
    "html","css","sass","graphql","rest api","linux","git","ci/cd","devops",
}
_MEDICAL_SKILLS = {
    "surgery","cardiology","pediatrics","psychiatry","nursing","dentistry",
    "pharmacy","radiology","oncology","orthopedics","general medicine",
    "anatomy","physiology","clinical research","patient care","icu",
}
_LEGAL_SKILLS = {
    "contract law","corporate law","criminal law","intellectual property",
    "litigation","legal research","compliance","gdpr","due diligence",
}
_CULINARY_SKILLS = {
    "cooking","pastry","baking","culinary","food safety","menu planning","catering",
}
_DESIGN_SKILLS = {
    "figma","adobe xd","sketch","photoshop","illustrator","ui design","ux design",
    "ui/ux","wireframing","prototyping","user research","motion design",
}


def skill_domain(skills: list[str]) -> str | None:
    """Return the dominant domain of a skill list, or None if mixed/unclear."""
    lower_skills = {s.lower() for s in skills}
    counts = {
        "tech": len(lower_skills & _TECH_SKILLS),
        "medical": len(lower_skills & _MEDICAL_SKILLS),
        "legal": len(lower_skills & _LEGAL_SKILLS),
        "culinary": len(lower_skills & _CULINARY_SKILLS),
        "design": len(lower_skills & _DESIGN_SKILLS),
    }
    best = max(counts, key=lambda k: counts[k])
    return best if counts[best] >= 2 else None
