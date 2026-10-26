# Online-Sport-Shop
SportZone is a responsive online sports shopping website featuring Cricket, Football, Running, Fitness, Badminton, and Basketball products with prices and descriptions. Built using Python Flask, SQLite, HTML, CSS, and JavaScript.

## Deploying on Render

1. Create a PostgreSQL database in Render and copy its **Internal Database URL**.
2. Create a Render Web Service for this repository, using `pip install -r requirements.txt` as the build command and `gunicorn app:app` as the start command.
3. In the Web Service's **Environment** settings, add `DATABASE_URL` with the database URL, and set `SECRET_KEY` to a strong random value.
4. Add `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` if you want to enable Razorpay payments, then deploy the service.

The app initializes its tables at startup and will fail to start if it cannot connect to the database. Render's local filesystem is ephemeral, so uploaded product images need persistent or object storage if they must survive redeploys.
