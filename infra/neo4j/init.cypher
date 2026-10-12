// Schema Constraints & Indexes for Healthcare Knowledge Graph

// Uniqueness Constraints
CREATE CONSTRAINT disease_id_unique IF NOT EXISTS FOR (d:Disease) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT symptom_id_unique IF NOT EXISTS FOR (s:Symptom) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT medication_id_unique IF NOT EXISTS FOR (m:Medication) REQUIRE m.id IS UNIQUE;
CREATE CONSTRAINT treatment_id_unique IF NOT EXISTS FOR (t:Treatment) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT labtest_id_unique IF NOT EXISTS FOR (l:LabTest) REQUIRE l.id IS UNIQUE;
CREATE CONSTRAINT document_id_unique IF NOT EXISTS FOR (doc:Document) REQUIRE doc.id IS UNIQUE;
CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE;

// Indexes for fast lookup by name
CREATE INDEX disease_name_idx IF NOT EXISTS FOR (d:Disease) ON (d.name);
CREATE INDEX symptom_name_idx IF NOT EXISTS FOR (s:Symptom) ON (s.name);
CREATE INDEX medication_name_idx IF NOT EXISTS FOR (m:Medication) ON (m.name);
CREATE INDEX treatment_name_idx IF NOT EXISTS FOR (t:Treatment) ON (t.name);
