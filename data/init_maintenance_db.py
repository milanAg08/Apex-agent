"""
Initializes the municipal maintenance database for Ward 34 (D.V. Gundappa Ward, Bengaluru).
Creates schema and seeds synthetic repair history, contractor records, defect liability terms,
and existing open tickets.
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "maintenance_db.sqlite")

def initialize_database(db_path: str = DB_PATH) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. Road Segments & Engineering Properties
    cur.execute("""
    CREATE TABLE IF NOT EXISTS segments (
        segment_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        road_class TEXT NOT NULL,
        traffic_index REAL NOT NULL,
        last_repair_date TEXT,
        contractor_name TEXT,
        layer_thickness_mm INTEGER,
        liability_period_years INTEGER,
        liability_expiry_date TEXT,
        repair_history_risk REAL DEFAULT 0.5,
        unit_rate_multiplier REAL DEFAULT 1.0
    );
    """)

    # 2. Historical Maintenance & Repair Records
    cur.execute("""
    CREATE TABLE IF NOT EXISTS repair_records (
        record_id TEXT PRIMARY KEY,
        segment_id TEXT NOT NULL,
        repair_date TEXT NOT NULL,
        contractor_name TEXT NOT NULL,
        scope_description TEXT NOT NULL,
        cost_inr REAL NOT NULL,
        layer_thickness_mm INTEGER NOT NULL,
        defect_liability_years INTEGER NOT NULL,
        defect_liability_end_date TEXT NOT NULL,
        FOREIGN KEY (segment_id) REFERENCES segments(segment_id)
    );
    """)

    # 3. Active / Open Civic Tickets (for Duplicate Merging - Branch A)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS open_tickets (
        ticket_id TEXT PRIMARY KEY,
        segment_id TEXT NOT NULL,
        lat REAL NOT NULL,
        lon REAL NOT NULL,
        reported_date TEXT NOT NULL,
        description TEXT NOT NULL,
        status TEXT NOT NULL,
        estimated_area_sqm REAL,
        priority TEXT,
        FOREIGN KEY (segment_id) REFERENCES segments(segment_id)
    );
    """)

    # Clear existing data for fresh seed
    cur.execute("DELETE FROM open_tickets;")
    cur.execute("DELETE FROM repair_records;")
    cur.execute("DELETE FROM segments;")

    # Seed Segments
    # Reference Date: late 2026 (current time ~ 2026-10)
    segments_data = [
        (
            "SEG_DVG_001",
            "D.V.G. Road (North Section)",
            "arterial",
            0.88,
            "2025-08-10",
            "Sri Lakshmi Infrastructure Ltd",
            50,   # >40mm: 3 years defect liability under BBMP 2021 Tender
            3,
            "2028-08-10",  # Active liability in 2026!
            0.85,
            1.25
        ),
        (
            "SEG_DVG_002",
            "D.V.G. Road (South Section)",
            "arterial",
            0.85,
            "2022-04-15",
            "Karnataka Road Builders Co",
            40,
            2,
            "2024-04-15",  # Expired liability
            0.60,
            1.25
        ),
        (
            "SEG_BULL_001",
            "Bull Temple Road (BMSCE Frontage)",
            "arterial",
            0.92,
            "2021-11-20",
            "Apex Infra Projects",
            50,
            3,
            "2024-11-20",  # Expired liability
            0.75,
            1.30
        ),
        (
            "SEG_GANDHI_001",
            "Gandhi Bazaar Main Road",
            "sub_arterial",
            0.78,
            "2025-11-05",
            "Sri Lakshmi Infrastructure Ltd",
            30,   # <40mm: 2 years defect liability
            2,
            "2027-11-05",  # Active liability in 2026!
            0.70,
            1.15
        ),
        (
            "SEG_BUGLE_001",
            "Bugle Rock Road",
            "collector",
            0.55,
            "2023-02-18",
            "Basaveshwara Civils",
            30,
            2,
            "2025-02-18",  # Expired
            0.40,
            1.00
        ),
        (
            "SEG_NETKAL_001",
            "Netkallappa Circle Approach",
            "sub_arterial",
            0.72,
            "2023-06-25",
            "Cauvery Engineering Works",
            35,
            2,
            "2025-06-25",  # Expired
            0.50,
            1.15
        ),
        (
            "SEG_LANE_001",
            "Basavanagudi 2nd Cross Residential",
            "local",
            0.28,
            "2020-03-10",
            "Local Ward Contractor",
            25,
            1,
            "2021-03-10",  # Expired
            0.20,
            0.85
        ),
        (
            "SEG_LANE_002",
            "Model House Street 1st Cross",
            "local",
            0.22,
            "2022-09-01",
            "Local Ward Contractor",
            25,
            1,
            "2023-09-01",  # Expired
            0.15,
            0.85
        ),
    ]

    cur.executemany("""
    INSERT INTO segments (
        segment_id, name, road_class, traffic_index, last_repair_date,
        contractor_name, layer_thickness_mm, liability_period_years,
        liability_expiry_date, repair_history_risk, unit_rate_multiplier
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, segments_data)

    # Seed Open Tickets (for Branch A - MERGE_DUPLICATE matching)
    open_tickets_data = [
        (
            "TKT_DVG_101",
            "SEG_DVG_001",
            12.9432,
            77.5738,
            "2026-10-25",
            "Severe crater-like pothole outside Upahara Darshini on DVG Road north, causing two-wheeler skids",
            "IN_PROGRESS",
            4.5,
            "P1"
        ),
        (
            "TKT_BULL_102",
            "SEG_BULL_001",
            12.9390,
            77.5688,
            "2026-10-24",
            "Series of potholes near BMSCE Main Gate, water ponding observed",
            "ASSIGNED_INSPECTION",
            8.0,
            "P2"
        ),
        (
            "TKT_GANDHI_103",
            "SEG_GANDHI_001",
            12.9438,
            77.5718,
            "2026-10-20",
            "Bitumen unraveling and rutting opposite Gandhi Bazaar market gate",
            "UNDER_REVIEW",
            3.0,
            "P3"
        )
    ]

    cur.executemany("""
    INSERT INTO open_tickets (
        ticket_id, segment_id, lat, lon, reported_date, description, status, estimated_area_sqm, priority
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, open_tickets_data)

    # Seed Detailed Repair Records
    records_data = [
        (
            "REP_2025_001",
            "SEG_DVG_001",
            "2025-08-10",
            "Sri Lakshmi Infrastructure Ltd",
            "Full-depth asphalt resurfacing (50mm BC over DBM)",
            450000.0,
            50,
            3,
            "2028-08-10"
        ),
        (
            "REP_2025_002",
            "SEG_GANDHI_001",
            "2025-11-05",
            "Sri Lakshmi Infrastructure Ltd",
            "Surface dressing and 30mm bituminous concrete overlay",
            280000.0,
            30,
            2,
            "2027-11-05"
        ),
        (
            "REP_2022_001",
            "SEG_DVG_002",
            "2022-04-15",
            "Karnataka Road Builders Co",
            "Periodic renewal course (40mm BC)",
            320000.0,
            40,
            2,
            "2024-04-15"
        )
    ]

    cur.executemany("""
    INSERT INTO repair_records (
        record_id, segment_id, repair_date, contractor_name, scope_description,
        cost_inr, layer_thickness_mm, defect_liability_years, defect_liability_end_date
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, records_data)

    conn.commit()
    conn.close()
    print(f"Maintenance DB successfully initialized at: {db_path}")

if __name__ == "__main__":
    initialize_database()
