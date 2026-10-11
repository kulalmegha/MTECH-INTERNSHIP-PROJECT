
CREATE TABLE users (
	id INTEGER NOT NULL, 
	username VARCHAR(80) NOT NULL, 
	password_hash VARCHAR(128) NOT NULL, 
	role VARCHAR(10) NOT NULL, 
	case_id INTEGER, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT fk_users_case_id FOREIGN KEY(case_id) REFERENCES cases (id) ON DELETE SET NULL
)

;


CREATE TABLE cases (
	id INTEGER NOT NULL, 
	case_code VARCHAR(20) NOT NULL, 
	consent_given BOOLEAN NOT NULL, 
	consent_timestamp DATETIME, 
	assigned_counsellor_id INTEGER, 
	follow_up_interval_days INTEGER NOT NULL, 
	next_follow_up_due DATETIME, 
	status VARCHAR(9) NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_cases_case_code UNIQUE (case_code), 
	CONSTRAINT ck_cases_consent CHECK (consent_given = 1 OR consent_given = true), 
	FOREIGN KEY(assigned_counsellor_id) REFERENCES users (id) ON DELETE SET NULL
)

;


CREATE TABLE checkins (
	id INTEGER NOT NULL, 
	case_id INTEGER NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	stress_level INTEGER NOT NULL, 
	feels_safe BOOLEAN NOT NULL, 
	faces_threat BOOLEAN NOT NULL, 
	sleep_difficulty BOOLEAN NOT NULL, 
	wants_counselling BOOLEAN NOT NULL, 
	free_text TEXT, 
	sentiment_label VARCHAR(20), 
	sentiment_score FLOAT, 
	emotion_label VARCHAR(30), 
	emotion_score FLOAT, 
	distress_score FLOAT, 
	distress_band VARCHAR(20), 
	score_breakdown JSON, 
	PRIMARY KEY (id), 
	FOREIGN KEY(case_id) REFERENCES cases (id) ON DELETE CASCADE
)

;


CREATE TABLE alerts (
	id INTEGER NOT NULL, 
	case_id INTEGER NOT NULL, 
	checkin_id INTEGER, 
	alert_type VARCHAR(50) NOT NULL, 
	reason TEXT NOT NULL, 
	status VARCHAR(8) NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	reviewed_by INTEGER, 
	reviewed_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(case_id) REFERENCES cases (id) ON DELETE CASCADE, 
	FOREIGN KEY(checkin_id) REFERENCES checkins (id) ON DELETE SET NULL, 
	FOREIGN KEY(reviewed_by) REFERENCES users (id) ON DELETE SET NULL
)

;


CREATE TABLE support_tags (
	id INTEGER NOT NULL, 
	checkin_id INTEGER NOT NULL, 
	category VARCHAR(80) NOT NULL, 
	suggested_by_system BOOLEAN NOT NULL, 
	approved_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(checkin_id) REFERENCES checkins (id) ON DELETE CASCADE, 
	FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE SET NULL
)

;


CREATE TABLE actions (
	id INTEGER NOT NULL, 
	alert_id INTEGER NOT NULL, 
	case_id INTEGER NOT NULL, 
	counsellor_id INTEGER NOT NULL, 
	action_taken TEXT NOT NULL, 
	contact_channel VARCHAR(50), 
	outcome TEXT, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(alert_id) REFERENCES alerts (id) ON DELETE CASCADE, 
	FOREIGN KEY(case_id) REFERENCES cases (id) ON DELETE CASCADE, 
	FOREIGN KEY(counsellor_id) REFERENCES users (id) ON DELETE CASCADE
)

;