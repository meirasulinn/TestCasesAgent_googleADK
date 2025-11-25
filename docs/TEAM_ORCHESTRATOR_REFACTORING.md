# Google ADK Team Orchestrator - Refactoring Summary

## מה השתנה?

### לפני (Custom Orchestration):
```python
class Orchestrator:
    def __init__(self, user_id):
        # קריאה ישירה לאייגנט ספציפי
        self.test_case_agent = TestCaseAgent(...)
    
    async def handle_chat(self, message):
        # לוגיקה ידנית להחלטה איזה אייגנט לקרוא
        result = await self.test_case_agent.process(...)
```

**בעיות:**
- ❌ קריאה ישירה וקשיחה ל-TestCaseAgent בשורה 100
- ❌ אין שימוש באורקסטרייטור המובנה של Google ADK
- ❌ קשה להוסיף אייגנטים נוספים
- ❌ אין ניתוב אוטומטי בין אייגנטים

---

### אחרי (Google ADK Team):
```python
from google.adk.agents import Team

class Orchestrator:
    def __init__(self, user_id):
        # רישום דינמי של אייגנטים
        self.agents: List[BaseAgent] = []
        self.team_agent: Optional[Team] = None
        self.runner: Optional[Runner] = None
    
    async def initialize(self):
        # רישום כל האייגנטים
        test_case_agent = TestCaseAgent(...)
        self.agents.append(test_case_agent)
        
        # יצירת Team עם כל ה-sub-agents
        sub_agents = [agent.create_adk_agent() for agent in self.agents]
        
        self.team_agent = Team(
            name=f"team_orchestrator_{self.user_id}",
            agents=sub_agents,
            instruction="You are a multi-agent orchestration system..."
        )
        
        # יצירת Runner ל-Team
        self.runner = Runner(
            agent=self.team_agent,
            session_service=self.adk_session_service,
            artifact_service=self.adk_artifact_service
        )
    
    async def handle_chat(self, message):
        # Team מחליט אוטומטית לאיזה אייגנט לנתב
        result = await self._run_team_agent(message)
```

**יתרונות:**
- ✅ שימוש ב-Google ADK Team (orchestrator מובנה)
- ✅ ניתוב אוטומטי בין אייגנטים על בסיס הבקשה
- ✅ קל להוסיף אייגנטים נוספים (פשוט `agents.append()`)
- ✅ התשתית גנרית ולא תלויה באייגנט ספציפי

---

## ארכיטקטורה חדשה

```
┌─────────────────────────────────────────────────┐
│           Orchestrator (per user)               │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │      Google ADK Team Agent              │   │
│  │  (Automatic routing & delegation)       │   │
│  └──────────────┬──────────────────────────┘   │
│                 │                               │
│                 │ Routes to:                    │
│                 │                               │
│      ┌──────────┴──────────┐                   │
│      │                     │                    │
│  ┌───▼────────┐    ┌──────▼──────┐            │
│  │ Test Case  │    │ Future      │            │
│  │ Agent      │    │ Agents...   │            │
│  │ (LlmAgent) │    │             │            │
│  └────────────┘    └─────────────┘            │
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │     Runner (ADK execution engine)       │   │
│  └─────────────────────────────────────────┘   │
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │  InMemorySessionService (ADK sessions)  │   │
│  └─────────────────────────────────────────┘   │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

## איך Team מחליט לאיזה אייגנט לנתב?

ה-Team Agent מקבל instruction שמגדיר את האייגנטים הזמינים:

```python
instruction="""You are a multi-agent orchestration system.

Your job is to analyze user requests and delegate to the most appropriate specialized agent:
- test_case_agent: For generating test cases from specifications

Always route to the correct agent based on the user's intent.
Provide clear, comprehensive responses based on the agent's output."""
```

Google ADK מנתח את בקשת המשתמש ובוחר את האייגנט המתאים אוטומטית!

---

## איך להוסיף אייגנט חדש?

### דוגמה: הוספת BugReportAgent

```python
# 1. צור את האייגנט החדש (יורש מ-BaseAgent)
class BugReportAgent(BaseAgent):
    def create_adk_agent(self) -> LlmAgent:
        return LlmAgent(
            model=LiteLlm(model="openai/gpt-4o-mini"),
            name="bug_report_agent",
            instruction="Generate detailed bug reports..."
        )

# 2. רשום אותו ב-Orchestrator.initialize()
async def initialize(self):
    # ... existing code ...
    
    # הוסף את האייגנט החדש
    bug_report_agent = BugReportAgent(
        user_id=self.user_id,
        session_manager=self.session_manager,
        faiss_service=self.faiss_service
    )
    self.agents.append(bug_report_agent)  # ← זהו זה!
    
    # עדכן את ה-instruction של Team
    self.team_agent = Team(
        agents=[agent.create_adk_agent() for agent in self.agents],
        instruction="""..."""
        - test_case_agent: For generating test cases
        - bug_report_agent: For creating bug reports  ← הוסף תיאור
        """
    )
```

זהו! Team יתחיל אוטומטית לנתב גם ל-BugReportAgent כשצריך.

---

## Flow דוגמה

### 1. User uploads file
```
User → API → Orchestrator.handle_file_upload()
                     ↓
              _run_team_agent(request)
                     ↓
              Runner.run_async()
                     ↓
              Team Agent analyzes request
                     ↓
              Routes to: test_case_agent
                     ↓
              TestCaseAgent.process()
                     ↓
              Return test cases ✓
```

### 2. User sends chat message
```
User → API → Orchestrator.handle_chat(message)
                     ↓
              Add context (files info)
                     ↓
              _run_team_agent(full_message)
                     ↓
              Runner.run_async()
                     ↓
              Team Agent analyzes request
                     ↓
              Routes to appropriate agent
                     ↓
              Collect events & responses
                     ↓
              Parse & return results ✓
```

---

## בדיקה

הרץ את הסקריפט לבדיקה:

```bash
python test_team_orchestrator.py
```

זה יבדוק:
- ✅ יצירת orchestrator עם Team
- ✅ ניתוב אוטומטי לאייגנט הנכון
- ✅ העלאת קובץ וגנרציה אוטומטית
- ✅ צ'אט עם קונטקסט

---

## סיכום

| היבט | לפני | אחרי |
|------|------|------|
| **Orchestration** | Custom logic | Google ADK Team |
| **Agent selection** | Hard-coded | Automatic routing |
| **Extensibility** | Low | High |
| **Pattern** | Manual | Pure ADK |
| **Agents** | Single | Multi-agent ready |

**התוצאה:** תשתית גנרית שמאפשרת הוספת אייגנטים נוספים בקלות, עם ניתוב אוטומטי ואינטליגנטי באמצעות Google ADK Team! 🎉
