// ============================================================
// Kavalx Advanced Fraud Detection & Banking Security
// Memgraph Schema Initialization
// ============================================================
// Run against: Memgraph v2.x+
// ============================================================

// --------------------------------------------------------
// Node Indexes – Account
// --------------------------------------------------------
CREATE INDEX ON :Account(id);
CREATE INDEX ON :Account(risk_score);
CREATE INDEX ON :Account(cluster_id);

// --------------------------------------------------------
// Node Indexes – Device
// --------------------------------------------------------
CREATE INDEX ON :Device(fingerprint);

// --------------------------------------------------------
// Edge Indexes – TRANSFERRED
// --------------------------------------------------------
CREATE EDGE INDEX ON :TRANSFERRED(timestamp);
CREATE EDGE INDEX ON :TRANSFERRED(tgn_edge_score);

// --------------------------------------------------------
// Uniqueness Constraints
// --------------------------------------------------------
CREATE CONSTRAINT ON (a:Account) ASSERT a.id IS UNIQUE;
CREATE CONSTRAINT ON (d:Device) ASSERT d.fingerprint IS UNIQUE;

// --------------------------------------------------------
// Additional Node Labels & Indexes for OSINT/APK
// --------------------------------------------------------
CREATE INDEX ON :UPIAddress(vpa);
CREATE INDEX ON :APK(sha256);
CREATE INDEX ON :Phone(number);
CREATE INDEX ON :IP(address);

// --------------------------------------------------------
// Edge Indexes – supplementary relationships
// --------------------------------------------------------
CREATE EDGE INDEX ON :USES_DEVICE;
CREATE EDGE INDEX ON :HAS_UPI;
CREATE EDGE INDEX ON :FLAGGED_BY;
