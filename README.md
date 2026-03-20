
Run backend:
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

Run frontend:
cd frontend
npm install
npm run dev

Steps:
1 upload PDF
2 call /index
3 call /query
