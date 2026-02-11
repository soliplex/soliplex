import logging
from unittest import mock

import pytest

from soliplex import loggers

LOGGER_NAME = "test-logger"


@pytest.mark.parametrize("w_extra", [{}, {"foo": "bar"}])
@mock.patch("logging.getLogger")
def test_logwrapper_ctor(lgl, w_extra):
    wrapper = loggers.LogWrapper(LOGGER_NAME, **w_extra)

    assert wrapper.logger is lgl.return_value
    assert wrapper.extra == w_extra

    lgl.assert_called_once_with(LOGGER_NAME)


@pytest.mark.parametrize("w_extra", [{}, {"foo": "bar"}])
@mock.patch("logging.getLogger")
def test_logwrapper_log(lgl, w_extra):
    wrapper = loggers.LogWrapper(LOGGER_NAME, **w_extra)
    logger = lgl.return_value

    wrapper.log(logging.DEBUG, "Foo: %s", "foo")

    logger.log.assert_called_once_with(
        logging.DEBUG,
        "Foo: %s",
        "foo",
        extra=w_extra,
    )


@pytest.mark.parametrize("w_extra", [{}, {"foo": "bar"}])
@mock.patch("logging.getLogger")
def test_logwrapper_critical(lgl, w_extra):
    wrapper = loggers.LogWrapper(LOGGER_NAME, **w_extra)
    logger = lgl.return_value

    wrapper.critical("Foo: %s", "foo")

    logger.critical.assert_called_once_with("Foo: %s", "foo", extra=w_extra)


@pytest.mark.parametrize("w_extra", [{}, {"foo": "bar"}])
@mock.patch("logging.getLogger")
def test_logwrapper_exception(lgl, w_extra):
    wrapper = loggers.LogWrapper(LOGGER_NAME, **w_extra)
    logger = lgl.return_value

    wrapper.exception("Foo: %s", "foo")

    logger.exception.assert_called_once_with("Foo: %s", "foo", extra=w_extra)


@pytest.mark.parametrize("w_extra", [{}, {"foo": "bar"}])
@mock.patch("logging.getLogger")
def test_logwrapper_error(lgl, w_extra):
    wrapper = loggers.LogWrapper(LOGGER_NAME, **w_extra)
    logger = lgl.return_value

    wrapper.error("Foo: %s", "foo")

    logger.error.assert_called_once_with("Foo: %s", "foo", extra=w_extra)


@pytest.mark.parametrize("w_extra", [{}, {"foo": "bar"}])
@mock.patch("logging.getLogger")
def test_logwrapper_warning(lgl, w_extra):
    wrapper = loggers.LogWrapper(LOGGER_NAME, **w_extra)
    logger = lgl.return_value

    wrapper.warning("Foo: %s", "foo")

    logger.warning.assert_called_once_with("Foo: %s", "foo", extra=w_extra)


@pytest.mark.parametrize("w_extra", [{}, {"foo": "bar"}])
@mock.patch("logging.getLogger")
def test_logwrapper_info(lgl, w_extra):
    wrapper = loggers.LogWrapper(LOGGER_NAME, **w_extra)
    logger = lgl.return_value

    wrapper.info("Foo: %s", "foo")

    logger.info.assert_called_once_with("Foo: %s", "foo", extra=w_extra)


@pytest.mark.parametrize("w_extra", [{}, {"foo": "bar"}])
@mock.patch("logging.getLogger")
def test_logwrapper_debug(lgl, w_extra):
    wrapper = loggers.LogWrapper(LOGGER_NAME, **w_extra)
    logger = lgl.return_value

    wrapper.debug("Foo: %s", "foo")

    logger.debug.assert_called_once_with("Foo: %s", "foo", extra=w_extra)


@pytest.mark.parametrize("w_extra", [{}, {"foo": "bar"}])
@pytest.mark.parametrize("w_new_name", [False, True])
@mock.patch("logging.getLogger")
def test_logwrapper_bind(lgl, w_new_name, w_extra):
    NEW_LOGGER_NAME = "new-name"
    wrapper = loggers.LogWrapper(LOGGER_NAME, spam="qux")
    lgl.reset_mock()

    if w_new_name:
        bound = wrapper.bind(NEW_LOGGER_NAME, **w_extra)
        exp_name = NEW_LOGGER_NAME
    else:
        bound = wrapper.bind(**w_extra)
        exp_name = LOGGER_NAME

    assert bound.logger_name == exp_name
    assert bound.extra == wrapper.extra | w_extra

    lgl.assert_called_once_with(exp_name)
