"""
Demo Script for Text-to-SQL Healthcare System
Demonstrates the complete functionality of the system
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.db_manager import DatabaseManager
from backend.text_to_sql import TextToSQLConverter
from backend.sql_validator import SQLValidator, SQLExecutor


def print_separator():
    """Print a visual separator"""
    print("\n" + "=" * 70 + "\n")


def demo_database_setup():
    """Demonstrate database setup and schema extraction"""
    print_separator()
    print("DATABASE SETUP DEMO")
    print_separator()
    
    # Initialize database manager
    db = DatabaseManager("database/healthcare.db")
    
    try:
        # Initialize database with schema and sample data
        print("Initializing database...")
        db.initialize_database()
        print("✓ Database initialized successfully")
    except Exception as e:
        print(f"Note: {e}")
        print("Database may already exist")
    
    # Get and display schema
    print("\nExtracting database schema...")
    schema = db.get_schema()
    
    print(f"✓ Found {len(schema['tables'])} tables:")
    for table_name in schema['tables'].keys():
        print(f"  - {table_name}")
    
    print(f"\n✓ Found {len(schema['relationships'])} relationships:")
    for rel in schema['relationships']:
        print(f"  - {rel['from_table']}.{rel['from_column']} → {rel['to_table']}.{rel['to_column']}")
    
    # Get schema for prompt
    print("\nSchema formatted for LLM prompts:")
    print("-" * 70)
    print(db.get_schema_for_prompt())
    print("-" * 70)
    
    return db


def demo_text_to_sql(db):
    """Demonstrate Text-to-SQL conversion"""
    print_separator()
    print("TEXT-TO-SQL CONVERSION DEMO")
    print_separator()
    
    # Initialize converter
    converter = TextToSQLConverter(db)
    
    # Test queries
    test_queries = [
        "Show all patients",
        "How many doctors are there",
        "Show patients where name is James",
        "List appointments from patients and doctors",
        "Display medical records",
        "Show prescriptions",
        "Count appointments by status"
    ]
    
    print("Converting natural language queries to SQL:\n")
    
    for i, query in enumerate(test_queries, 1):
        print(f"{i}. Natural Language: {query}")
        sql = converter.convert(query)
        print(f"   Generated SQL: {sql}")
        print()


def demo_sql_validation(db):
    """Demonstrate SQL validation"""
    print_separator()
    print("SQL VALIDATION DEMO")
    print_separator()
    
    validator = SQLValidator(db)
    
    # Test queries
    test_queries = [
        ("SELECT * FROM patients", True),
        ("SELECT * FROM invalid_table", False),
        ("SELECT invalid_column FROM patients", False),
        ("DROP TABLE patients", False),
        ("DELETE FROM patients", False),
        ("SELECT first_name, last_name FROM patients", True)
    ]
    
    print("Validating SQL queries:\n")
    
    for sql, expected_valid in test_queries:
        is_valid, error = validator.validate(sql)
        status = "✓ Valid" if is_valid else "✗ Invalid"
        print(f"SQL: {sql}")
        print(f"Result: {status}")
        if error:
            print(f"Error: {error}")
        print()


def demo_query_execution(db):
    """Demonstrate query execution"""
    print_separator()
    print("QUERY EXECUTION DEMO")
    print_separator()
    
    validator = SQLValidator(db)
    executor = SQLExecutor(db, validator)
    
    # Test queries
    test_queries = [
        "SELECT * FROM patients LIMIT 3",
        "SELECT COUNT(*) as doctor_count FROM doctors",
        "SELECT d.department_name, COUNT(*) as doctor_count FROM departments d LEFT JOIN doctors doc ON d.department_id = doc.department_id GROUP BY d.department_name"
    ]
    
    print("Executing SQL queries:\n")
    
    for sql in test_queries:
        print(f"SQL: {sql}")
        success, result, error = executor.execute(sql)
        
        if success:
            print(f"✓ Success - {len(result)} rows returned")
            if result:
                print("Sample results:")
                for row in result[:2]:  # Show first 2 rows
                    print(f"  {row}")
        else:
            print(f"✗ Failed: {error}")
        print()


def demo_complete_pipeline(db):
    """Demonstrate complete pipeline: natural language → SQL → execution"""
    print_separator()
    print("COMPLETE PIPELINE DEMO")
    print_separator()
    
    converter = TextToSQLConverter(db)
    validator = SQLValidator(db)
    executor = SQLExecutor(db, validator)
    
    # Test natural language queries
    test_queries = [
        "Show all patients",
        "How many doctors are there?",
        "List the departments"
    ]
    
    print("Complete pipeline: Natural Language → SQL → Results\n")
    
    for query in test_queries:
        print(f"Natural Language: {query}")
        
        # Convert to SQL
        sql = converter.convert(query)
        print(f"Generated SQL: {sql}")
        
        # Validate
        is_valid, error = validator.validate(sql)
        print(f"Validation: {'✓ Valid' if is_valid else '✗ Invalid'}")
        
        # Execute
        if is_valid:
            success, result, error = executor.execute(sql)
            if success:
                print(f"✓ Execution successful - {len(result)} rows")
                if result:
                    print("Results:")
                    for row in result[:2]:
                        print(f"  {row}")
            else:
                print(f"✗ Execution failed: {error}")
        else:
            print(f"Validation error: {error}")
        
        print()


def demo_api_usage():
    """Demonstrate API usage examples"""
    print_separator()
    print("API USAGE EXAMPLES")
    print_separator()
    
    print("The system provides a REST API with the following endpoints:\n")
    
    endpoints = [
        ("GET /api/schema", "Get database schema"),
        ("POST /api/convert", "Convert natural language to SQL"),
        ("POST /api/execute", "Execute SQL query"),
        ("POST /api/query", "Complete pipeline (convert + execute)"),
        ("GET /api/tables", "List all tables"),
        ("GET /api/table/<name>", "Get sample data from table"),
        ("POST /api/validate", "Validate SQL query"),
        ("GET /api/health", "Health check")
    ]
    
    for endpoint, description in endpoints:
        print(f"{endpoint:40} - {description}")
    
    print("\nExample API calls:")
    print("-" * 70)
    
    examples = [
        """# Convert natural language to SQL
curl -X POST http://localhost:5000/api/convert \\
  -H "Content-Type: application/json" \\
  -d '{"query": "Show all patients"}'""",
        
        """# Execute SQL query
curl -X POST http://localhost:5000/api/execute \\
  -H "Content-Type: application/json" \\
  -d '{"sql": "SELECT * FROM patients LIMIT 10"}'""",
        
        """# Complete pipeline
curl -X POST http://localhost:5000/api/query \\
  -H "Content-Type: application/json" \\
  -d '{"query": "How many doctors are there?""}'""",
        
        """# Get database schema
curl http://localhost:5000/api/schema"""
    ]
    
    for example in examples:
        print(example)
        print()


def main():
    """Run all demos"""
    print("\n" + "=" * 70)
    print("TEXT-TO-SQL HEALTHCARE SYSTEM - DEMONSTRATION")
    print("=" * 70)
    
    try:
        # Database setup
        db = demo_database_setup()
        
        # Text-to-SQL conversion
        demo_text_to_sql(db)
        
        # SQL validation
        demo_sql_validation(db)
        
        # Query execution
        demo_query_execution(db)
        
        # Complete pipeline
        demo_complete_pipeline(db)
        
        # API usage
        demo_api_usage()
        
        print_separator()
        print("DEMO COMPLETE")
        print_separator()
        print("\nTo start the web server, run:")
        print("  python backend/app.py")
        print("\nThen open your browser to:")
        print("  http://localhost:5000")
        print("\nTo run tests, execute:")
        print("  pytest tests/")
        print()
        
    except Exception as e:
        print(f"\n✗ Error during demo: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
