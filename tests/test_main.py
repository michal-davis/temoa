"""
quick test of some of the argument parsing
"""
import pytest

import main


# Written by:  J. F. Hyink
# jeff@westernspark.us
# https://westernspark.us
# Created on:  11/26/23
def test_parse_args(tmp_path, capsys):
    config_file = tmp_path / 'config.toml'
    config_file.write_text('nada')

    # missing config
    with pytest.raises(AttributeError) as e:
        main.parse_args(''.split())

    # bad file
    with pytest.raises(FileNotFoundError) as e:
        main.parse_args('--config sasquatch_bait.toml'.split())

    # good file
    main.parse_args(f'--config {config_file}'.split())

    # good output path
    options = main.parse_args(f'--config {config_file} --output_path {tmp_path}'.split())
    assert options.output_path == tmp_path

    # bad output path
    with pytest.raises(FileNotFoundError) as e:
        main.parse_args(f'--config {config_file} --output_path big_bird'.split())


    # options setting
    options = main.parse_args(f'--config {config_file} -s -d -b'.split())
    assert all((
        options.silent,
        options.debug,
        options.build_only
    ))
