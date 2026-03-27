# The Compliance Clerk

Command-first setup and execution guide.

## 1) Clone Repository
```powershell
git clone https://github.com/LakshayBaijal/The-Compliance-Clerk.git
cd The-Compliance-Clerk
```

## 2) Create Virtual Environment
```powershell
python -m venv venv
```

## 3) Activate Virtual Environment (Windows PowerShell)
```powershell
.\venv\Scripts\Activate.ps1
```

## 4) Install Dependencies
```powershell
pip install -r requirements.txt
```

## 5) Create Environment File
```powershell
copy .env.example .env
```

## 6) Add API Key in `.env`
Set this value manually in `.env`:
```env
GROQ_API_KEY=your_groq_api_key_here
```

## 7) Run Tests One by One
```powershell
python tests/test_schemas.py
python tests/test_ingest.py
python tests/test_classify.py
python tests/test_extractors.py
```

## 8) (Optional) Run All with `pytest`
```powershell
pytest -q
```

## 9) Git Workflow Used in This Project
```powershell
git add -A
git commit -m "your commit message"
git push
```

## Current Verified Test Status
- Schemas: `7/7` pass
- Ingest: `8/8` pass
- Classify: `10/10` pass
- Extractors: `12/12` pass
- Total: `37/37` pass
