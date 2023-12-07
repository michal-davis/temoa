"""
A series of tests focused on the model entity.
"""
import pathlib
import pickle

import pytest

from definitions import PROJECT_ROOT
from temoa.temoa_model.temoa_mode import TemoaMode
from temoa.temoa_model.temoa_sequencer import TemoaSequencer


# Written by:  J. F. Hyink
# jeff@westernspark.us
# https://westernspark.us
# Created on:  12/6/23
@pytest.mark.skip('not yet clear if this is needed/required ATT, researching mpi4py')
def test_pickle():
    """
    Test to ensure the model pickles properly.  This is used when employing mpi4py which requires
    that jobs passed are pickle-able
    """
    config_file = 'config_utopia.toml'
    config_file = pathlib.Path(PROJECT_ROOT, 'tests', 'testing_configs', config_file)
    output_path = pathlib.Path(PROJECT_ROOT, 'tests', 'testing_outputs')
    options = {'silent': True, 'debug': True}
    ts = TemoaSequencer(config_file=config_file,
                        output_path=output_path,
                        mode_override=TemoaMode.BUILD_ONLY,
                        **options)

    built_instance = ts.start()

    pickled_model = pickle.dumps(built_instance)
    assert pickled_model, 'model should have pickled successfully, but did not.'

    recovered_model = pickle.loads(pickled_model)
    assert recovered_model == pickled_model, 'Recovered model does not match original.'
