-- add the unlimited capacity flag to the technologies table
ALTER TABLE technologies
    ADD unlim_cap INTEGER;

-- update the commodity flags.  REPLACE acts like "insert if not already there..."
REPLACE INTO main.commodity_labels VALUES ('s', 'source commodity')

