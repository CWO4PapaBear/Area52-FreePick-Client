CREATE TABLE IF NOT EXISTS area52_enrollment_receipt (
  request_id char(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  username varchar(16) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  account_id int unsigned DEFAULT NULL,
  PRIMARY KEY (request_id),
  UNIQUE KEY enrollment_account (account_id),
  CONSTRAINT enrollment_account_fk FOREIGN KEY (account_id) REFERENCES account(id)
) ENGINE=InnoDB;
