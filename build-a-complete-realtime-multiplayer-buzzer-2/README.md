# Realtime Multiplayer Buzzer Competition

Complete realtime buzzer app with a static Netlify-ready frontend and a Flask-SocketIO backend deployable on Render.

## Project Structure

```text
project/
├── backend/
│   ├── app.py
│   ├── requirements.txt
│   ├── Procfile
│   ├── render.yaml
│   ├── supabase_schema.sql
│   └── .env.example
└── frontend/
    ├── index.html
    ├── room.html
    ├── style.css
    ├── app.js
    ├── room.js
    └── assets/
```

## Supabase Setup

1. Create a free Supabase project.
2. Open the SQL Editor.
3. Paste and run the full SQL from `backend/supabase_schema.sql`.
4. Go to Project Settings > API.
5. Copy:
   - Project URL as `SUPABASE_URL`
   - `service_role` key as `SUPABASE_SERVICE_ROLE_KEY`

The service role key must only be used by the Flask backend. Do not place it in frontend files.

## Local Backend Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `backend/.env`:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
FRONTEND_ORIGINS=http://localhost:5500,http://127.0.0.1:5500
SECRET_KEY=replace-with-a-long-random-string
PORT=5000
```

Run the backend:

```bash
python app.py
```

## Local Frontend Setup

The frontend is static. Serve it from the `frontend` folder with any static server:

```bash
cd frontend
python -m http.server 5500
```

Open:

```text
http://localhost:5500
```

The frontend defaults to `http://localhost:5000` when running locally.

## Render Backend Deployment

1. Push this project to GitHub.
2. In Render, create a new Web Service.
3. Select the repository.
4. Set the root directory to `backend`.
5. Render can use `backend/render.yaml`, or configure manually:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn --worker-class eventlet -w 1 app:app`
6. Add environment variables:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
FRONTEND_ORIGINS=https://your-netlify-site.netlify.app
SECRET_KEY=replace-with-a-long-random-string
PYTHON_VERSION=3.11.9
```

After deploy, copy the Render backend URL, for example:

```text
https://your-buzzer-backend.onrender.com
```

## Netlify Frontend Deployment

1. In Netlify, create a new site from GitHub.
2. Set the publish directory to `frontend`.
3. Leave build command empty.
4. Deploy.
5. Open your Netlify URL once with the backend URL:

```text
https://your-netlify-site.netlify.app?server=https://your-buzzer-backend.onrender.com
```

The frontend stores that backend URL in browser local storage. You can also paste or change the backend URL from the setup panel if it is missing.

## Socket Events

The backend implements:

- `create_room`
- `join_room`
- `player_joined`
- `buzz`
- `winner_selected`
- `reset_round`
- `scoreboard_update`

## Race Condition Protection

The backend validates every buzz server-side and uses a per-room lock plus a conditional Supabase update that only sets `current_winner_player_id` when it is still `NULL`. The frontend never decides the winner.

