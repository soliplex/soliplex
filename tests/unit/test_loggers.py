import contextlib
import logging
from unittest import mock

import pytest

from soliplex import installation
from soliplex import loggers

LOGGER_NAME = "test-logger"


@pytest.fixture
def the_installation():
    return mock.create_autospec(installation.Installation)


@pytest.mark.parametrize("w_extra", [{}, {"foo": "bar"}])
@mock.patch("logging.getLogger")
def test_logwrapper_ctor(lgl, the_installation, w_extra):
    wrapper = loggers.LogWrapper(LOGGER_NAME, the_installation, **w_extra)

    assert wrapper.logger is lgl.return_value
    assert wrapper.extra == w_extra

    lgl.assert_called_once_with(LOGGER_NAME)


@pytest.mark.parametrize("w_extra", [{}, {"foo": "bar"}])
@pytest.mark.parametrize("w_new_name", [False, True])
@mock.patch("logging.getLogger")
def test_logwrapper_bind(lgl, w_new_name, the_installation, w_extra):
    NEW_LOGGER_NAME = "new-name"
    wrapper = loggers.LogWrapper(LOGGER_NAME, the_installation, spam="qux")
    lgl.reset_mock()

    if w_new_name:
        bound = wrapper.bind(NEW_LOGGER_NAME, **w_extra)
        exp_name = NEW_LOGGER_NAME
    else:
        bound = wrapper.bind(**w_extra)
        exp_name = LOGGER_NAME

    assert bound.logger_name == exp_name
    assert bound.installation is the_installation
    assert bound.extra == wrapper.extra | w_extra

    lgl.assert_called_once_with(exp_name)


@pytest.mark.parametrize(
    "w_levels, expectation",
    [
        ({}, pytest.raises(loggers.UpdateLevelsEmpty)),
        (
            {10: 20, "TRACE": "INFO"},
            pytest.raises(loggers.UpdateLevelsInvalidKeyTypes),
        ),
        ({10: "INFO"}, pytest.raises(loggers.UpdateLevelsInvalidValueTypes)),
        ({10: 20}, contextlib.nullcontext({10: 20})),
        ({"DEBUG": "INFO"}, contextlib.nullcontext({10: 20})),
    ],
)
def test_updatelevels_ctor(w_levels, expectation):
    with expectation as expected:
        found = loggers.UpdateLevels(w_levels)

    if not isinstance(expected, pytest.ExceptionInfo):
        assert found._update_levels == expected


def _make_record(level):
    return logging.LogRecord(
        name="",
        level=level,
        pathname="/",
        lineno=1234,
        msg="testing",
        args=(),
        exc_info=False,
    )


@pytest.mark.parametrize(
    "w_level, exp_level",
    [
        (5, 5),
        (10, 20),
        (15, 15),
        (20, 20),
    ],
)
def test_updatelevels_filter(w_level, exp_level):
    record = _make_record(w_level)
    update_levels = loggers.UpdateLevels({10: 20})

    found = update_levels.filter(record)

    assert found.levelno == exp_level
