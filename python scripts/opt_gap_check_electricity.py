import sqlite3
import os



def find_sqlite_file(directory):
    """
    Finds the first SQLite file in the specified directory.

    Args:
        directory (str): The path to the directory to search.

    Returns:
        str: The path to the first SQLite file found in the directory, or None if no SQLite file is found.
    """
    # List all files in the directory
    files = os.listdir(directory)
    
    # Filter files to find the one with .sqlite extension
    sqlite_files = [f for f in files if f.endswith('.sqlite')]
    
    # Return the path to the first SQLite file found, or None if no file is found
    if sqlite_files:
        return os.path.join(directory, sqlite_files[0])
    else:
        return None

# Define the file paths for the source and target SQLite databases

source_db_path = find_sqlite_file('input_sqlite')
target_db_path = find_sqlite_file('output_sqlite')

if source_db_path:
    print(f"Found SQLite file: {source_db_path}")
else:
    print("No SQLite file found in the directory.")

if target_db_path:
    print(f"Found SQLite file: {source_db_path}")
else:
    print("No SQLite file found in the directory.")



def transfer_data():
    # Connect to the source SQLite database
    source_conn = sqlite3.connect(source_db_path)
    source_cursor = source_conn.cursor()
    
    # Connect to the target SQLite database
    target_conn = sqlite3.connect(target_db_path)
    target_cursor = target_conn.cursor()

    #set technologies to include in transfer
    keep_techs = ('E_BIO_M-NEW', 'E_NG_CCS-NEW', 'E_NG_CT-NEW', 'E_NUC_PWR-NEW', 
               'E_NUC_SMR-NEW', 'E_SOL_PV-NEW-1', 'E_SOL_PV-NEW-2', 'E_SOL_PV-NEW-3', 'E_SOL_PV-NEW-4', 'E_SOL_PV-NEW-5', 'E_SOL_PV-NEW-6', 
               'E_SOL_PV-NEW-7', 'E_SOL_PV-NEW-8', 'E_SOL_PV-NEW-9', 'E_SOL_PV-NEW-10', 
               'E_WND_ON-NEW-1', 'E_WND_ON-NEW-2', 'E_WND_ON-NEW-3', 'E_WND_ON-NEW-4', 
               'E_WND_ON-NEW-5', 'E_WND_ON-NEW-6', 'E_WND_ON-NEW-7', 'E_WND_ON-NEW-8', 
               'E_WND_ON-NEW-9', 'E_WND_ON-NEW-10', 'E_WND_ON-NEW-11','E_WND_ON-NEW-12','E_WND_ON-NEW-13',
               'E_BAT_2H-NEW','E_BAT_4H-NEW','E_NG_CCS_RFIT_90','E_NG_CCS_RFIT_95')
    # Fetch data from the 'Output_CapacityByPeriodAndTech' table in the source database
    source_cursor.execute(f'SELECT regions, scenario, sector, t_periods, tech, capacity FROM Output_CapacityByPeriodAndTech WHERE tech IN {keep_techs}')
    data = source_cursor.fetchall()
    
    # Define a function to insert data into the target tables
    def insert_into_target_table(table_name, data, table_type):
        # Define the SQL insertion command for the target tables
        insert_query = f'''
        REPLACE INTO {table_name} (regions, periods, tech, {table_type}cap, {table_type}cap_units, {table_type}cap_notes, reference, data_year, data_flags, dq_est, dq_rel, dq_comp, dq_time, dq_geog, dq_tech, additional_notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''

        prepared_data = []
        for row in data:
            regions, scenario, sector, t_periods, tech, capacity= row
            # For simplicity, fill in default values for columns that are not in the source table
            # Adjust as needed based on actual requirements
            prepared_data.append((
                regions,  # region
                t_periods,  # period (for example, current year; adjust as needed)
                tech,    # tech
                capacity,  # max_cap or min_cap (using capacity as max_cap/min_cap)
                'units',  # units (default value, adjust as needed)
                'N/A',  # notes (default value, adjust as needed)
                'N/A',  # reference (default value, adjust as needed)
                'N/A',  # data_years (default value, adjust as needed)
                'N/A',  # data_flags (default value, adjust as needed)
                'N/A',  # dq_est (default value, adjust as needed)
                'N/A',  # dq_rel (default value, adjust as needed)
                'N/A',  # dq_comp (default value, adjust as needed)
                'N/A',  # dq_time (default value, adjust as needed)
                'N/A',  # dq_geog (default value, adjust as needed)
                'N/A',  # dq_tech (default value, adjust as needed)
                'N/A'   # additional_notes (default value, adjust as needed)
            ))
        
        # Execute the insertion query with the prepared data
        target_cursor.executemany(insert_query, prepared_data)
        target_conn.commit()
    
    # Insert data into both 'MinCapacity' and 'MaxCapacity' tables
    insert_into_target_table('MinCapacity', data, 'min')
    insert_into_target_table('MaxCapacity', data, 'max')
    
    # Close the connections
    source_conn.close()
    target_conn.close()
    print("Data transfer completed successfully.")

# Run the data transfer function
if __name__ == "__main__":
    transfer_data()