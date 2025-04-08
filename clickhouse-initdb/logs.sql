CREATE DATABASE IF NOT EXISTS logger;
CREATE TABLE IF NOT EXISTS logger.apache_logs (
    ip String,
    timestamp DateTime,
    method String,
    path String,
    protocol String,
    status UInt16,
    bytes_sent UInt32,
    referrer String,
    user_agent String,
    response_time UInt32
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, ip);