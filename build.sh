#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Collecting static files..."
python manage.py collectstatic --no-input

echo "Running migrations..."
python manage.py migrate

echo "Seeding data..."
# Run custom populate scripts to seed initial database info (movies and foods)
python manage.py shell -c "
from api.models import City
if not City.objects.exists():
    import populate_movies
    import populate_food
"
