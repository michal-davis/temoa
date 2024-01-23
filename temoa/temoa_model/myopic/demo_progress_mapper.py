"""
Tools for Energy Model Optimization and Analysis (Temoa):
An open source framework for energy systems optimization modeling

Copyright (C) 2015,  NC State University

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

A complete copy of the GNU General Public License v2 (GPLv2) is available
in LICENSE.txt.  Users uncompressing this from an archive may not have
received this license file.  If not, see <http://www.gnu.org/licenses/>.


Written by:  J. F. Hyink
jeff@westernspark.us
https://westernspark.us
Created on:  1/22/24

"""
from temoa.temoa_model.myopic.myopic_index import MyopicIndex
from temoa.temoa_model.myopic.myopic_progress_mapper import MyopicProgressMapper
from temoa.temoa_model.myopic.myopic_sequencer import MyopicSequencer

fy = [2000, 2010, 2020, 2030, 2040, 2050, 2060]
mapper = MyopicProgressMapper(fy)
mapper.draw_header()
mapper.report(MyopicIndex(2020, 2040, 2050, 2060), 'load')
mapper.report(MyopicIndex(2020, 2040, 2050, 2060), 'solve')
mapper.report(MyopicIndex(2020, 2040, 2050, 2060), 'report')
next_mi = MyopicIndex(2040, 2060, 2050, 2060)
mapper.report(next_mi, 'load')
mapper.report(next_mi, 'solve')
mapper.report(next_mi, 'report')

print('\n' * 4)
# let's exercise the sequencer's version to be sure.
fy = [2000, 2010, 2020, 2030, 2040, 2050, 2060, 2070, 2080, 2090]
mapper = MyopicProgressMapper(fy)


class MockConfig:
    pass


config = MockConfig()
config.silent = False
config.myopic_inputs = {'view_depth': 4, 'step_size': 2}

sequencer = MyopicSequencer(config)
sequencer.characterize_run(fy)
while len(sequencer.instance_queue) > 0:
    mi = sequencer.instance_queue.pop()
    mapper.report(mi, 'load')
    mapper.report(mi, 'solve')
    mapper.report(mi, 'report')
