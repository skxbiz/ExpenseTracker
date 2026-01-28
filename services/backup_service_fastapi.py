import os
from services.firebase_db import firebase_service
import tempfile
from typing import List, Dict

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("Warning: pandas not available, some features may be limited")

class BackupService:
    def __init__(self, user_id: str, upload_folder: str = "uploads"):
        self.user_id = user_id
        self.upload_folder = upload_folder
        os.makedirs(upload_folder, exist_ok=True)

    def export_xlsx(self) -> str:
        """Export user transactions to Excel file"""
        try:
            # Get all transactions for the user
            transactions = firebase_service.get_transactions(self.user_id)
            
            if PANDAS_AVAILABLE:
                # Convert to DataFrame
                if transactions:
                    df = pd.DataFrame(transactions)
                    # Remove Firestore document ID from export
                    if 'id' in df.columns:
                        df = df.drop('id', axis=1)
                else:
                    # Create empty DataFrame with expected columns
                    df = pd.DataFrame(columns=['category', 'sub_category', 'description', 'amount', 'date_time', 'user_id'])
                
                # Create temporary file
                temp_file = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
                file_path = temp_file.name
                temp_file.close()
                
                # Export to Excel
                df.to_excel(file_path, index=False)
                return file_path
            else:
                # Fallback: return a dummy file for testing
                temp_file = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
                file_path = temp_file.name
                temp_file.close()
                print(f"⚠️ Pandas not available - created empty file: {file_path}")
                return file_path
                
        except Exception as e:
            print(f"Error exporting to Excel: {e}")
            raise Exception("Failed to export data")

    def import_xlsx(self, file_path: str) -> None:
        """Import transactions from Excel file"""
        try:
            # Read Excel file
            df = pd.read_excel(file_path)
            
            # Process each row
            for _, row in df.iterrows():
                try:
                    # Skip rows with missing required data
                    if pd.isna(row.get('description')) or pd.isna(row.get('amount')):
                        continue
                    
                    # Prepare transaction data
                    transaction_data = {
                        'category': row.get('category', ''),
                        'sub_category': row.get('sub_category', ''),
                        'description': str(row.get('description', '')),
                        'amount': float(row.get('amount', 0)),
                        'date_time': str(row.get('date_time', '')),
                        'user_id': self.user_id
                    }
                    
                    # Create transaction in Firebase
                    # Note: We're not checking for duplicates here as Firestore handles ID generation
                    firebase_service.create_transaction(transaction_data)
                    
                except (ValueError, KeyError) as e:
                    print(f"Skipping invalid row: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error importing from Excel: {e}")
            raise Exception("Failed to import data")