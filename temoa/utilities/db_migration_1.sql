-- add the unlimited capacity flag to the technologies table
ALTER TABLE technologies
    ADD unlim_cap INTEGER;

-- update the commodity flags.  REPLACE acts like "insert if not already there..."
REPLACE INTO main.commodity_labels VALUES ('s', 'source commodity');


-- fix the FK assignment in OutputEmissions to ref the commodity table.  (the old ref was not a unique index)
create table Output_Emissions_dg_tmp
(
    regions        text,
    scenario       text,
    sector         text,
    t_periods      integer,
    emissions_comm text,
    tech           text,
    vintage        integer,
    emissions      real,
    primary key (regions, scenario, t_periods, emissions_comm, tech, vintage),
    foreign key (sector) references sector_labels,
    foreign key (t_periods) references time_periods,
    foreign key (emissions_comm) references commodities,
    foreign key (tech) references technologies,
    foreign key (vintage) references time_periods
);

insert into Output_Emissions_dg_tmp(regions, scenario, sector, t_periods, emissions_comm, tech, vintage, emissions)
select regions,
       scenario,
       sector,
       t_periods,
       emissions_comm,
       tech,
       vintage,
       emissions
from Output_Emissions;

drop table Output_Emissions;

alter table Output_Emissions_dg_tmp
    rename to Output_Emissions;

-- turn on FK enforcement
PRAGMA FOREIGN_KEYS = 1;



