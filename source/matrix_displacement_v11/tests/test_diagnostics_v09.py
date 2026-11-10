from matrix_displacement.diagnostics import explain_error


def test_singular_suggests_support_check():
    message = explain_error(ValueError('Singular stiffness matrix: check supports'))
    assert message.title == '结构不稳定或约束不足'
    assert '支座' in message.detail
    assert 'ValueError:' in message.detail


def test_invalid_beam_explains_scope():
    message = explain_error(ValueError('Beam2D must be horizontal'))
    assert 'Frame2D' in message.detail


def test_nan_warning_and_original_exception():
    message = explain_error(ValueError('X must be a finite real number'))
    assert 'NaN' in message.detail
    assert 'finite real number' in message.detail


def test_unknown_error_does_not_hide_details():
    message = explain_error(RuntimeError('specific custom failure'))
    assert 'RuntimeError: specific custom failure' in message.detail
