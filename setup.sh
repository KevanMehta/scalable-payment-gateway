#!/bin/bash
# Initialize the system
docker-compose up -d --build

# Wait for services
sleep 15 

# Run migrations
docker-compose exec api python manage.py migrate

# Load test data
docker-compose exec postgres psql -U postgres -c "INSERT INTO..."

echo "✅ System ready! Access endpoints:"
echo "http://localhost:8000/docs"