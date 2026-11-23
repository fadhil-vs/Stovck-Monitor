# Stock Monitor

A minimal, mobile-first stock and sales management web application built with Python Flask, Supabase (PostgreSQL), and Tailwind CSS.

---

## 1. Setup Supabase Database

1. Log in to [Supabase](https://supabase.com) and open your project.
2. In the left navigation, click on **SQL Editor** -> **New query**.
3. Open `schema.sql` from this repository, copy the contents, paste it into the SQL editor, and click **Run**.
4. This creates the three tables:
   - `stock` (inventory levels)
   - `stock_orders` (history of added stock entries)
   - `sales` (bills with paid, unpaid, and not dealing statuses)

---

## 2. Deploy on Vercel

### Step A: Push to GitHub
1. Initialize git and commit your files (the `.env` file is already in `.gitignore`):
   ```bash
   git add .
   git commit -m "Initial commit for Vercel deployment"
   git push origin main
   ```

### Step B: Import Project in Vercel
1. Go to [vercel.com](https://vercel.com) and sign in.
2. Click **Add New...** -> **Project**.
3. Connect your GitHub repository and select this project.

### Step C: Add Environment Variables in Vercel
Before clicking **Deploy**, expand the **Environment Variables** section and add:

| Key | Value Example | Where to find |
|---|---|---|
| `SUPABASE_URL` | `https://your-project.supabase.co` | Supabase -> Settings -> API -> Project URL |
| `SUPABASE_KEY` | `your-service-role-secret-key` | Supabase -> Settings -> API -> Legacy API keys (`service_role` secret) |
| `FLASK_SECRET_KEY` | `your-random-flask-secret` | Generated random key |
| `CURRENCY_SYMBOL` | `₹` | Currency symbol (default: ₹) |

4. Click **Deploy**. Vercel will build and deploy the app with a live URL (e.g. `https://your-project.vercel.app`).

---

## 3. Local Development

To run locally:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
flask run --host=0.0.0.0 --port=5000
```
Open [http://localhost:5000](http://localhost:5000) in your browser.
