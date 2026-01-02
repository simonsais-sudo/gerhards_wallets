#!/bin/bash
# Database setup script for Influencer Tracker

set -e

echo "🗄️  Setting up PostgreSQL database for Influencer Tracker..."

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "❌ PostgreSQL is not installed. Installing..."
    sudo apt-get update
    sudo apt-get install -y postgresql postgresql-contrib
fi

# Start PostgreSQL if not running
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and user
echo "📝 Creating database and user..."

sudo -u postgres psql << EOF
-- Drop existing database if exists (careful!)
-- DROP DATABASE IF EXISTS influencer_tracker;
-- DROP USER IF EXISTS tracker;

-- Create user
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'tracker') THEN
        CREATE USER tracker WITH PASSWORD 'tracker_password';
    END IF;
END
\$\$;

-- Create database
SELECT 'CREATE DATABASE influencer_tracker OWNER tracker'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'influencer_tracker')\gexec

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE influencer_tracker TO tracker;

\c influencer_tracker

-- Grant schema privileges
GRANT ALL ON SCHEMA public TO tracker;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO tracker;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO tracker;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO tracker;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO tracker;

EOF

echo "✅ Database 'influencer_tracker' created successfully!"
echo "✅ User 'tracker' created with password 'tracker_password'"
echo ""
echo "📊 Connection string:"
echo "postgresql+asyncpg://tracker:tracker_password@localhost:5432/influencer_tracker"
echo ""
echo "🔧 Testing connection..."

# Test connection
PGPASSWORD=tracker_password psql -h localhost -U tracker -d influencer_tracker -c "SELECT version();" && echo "✅ Connection successful!"

echo ""
echo "🚀 Database is ready! Run 'python3 src/main.py' to initialize tables."
