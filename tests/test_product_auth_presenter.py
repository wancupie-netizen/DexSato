from presentation.product_auth_presenter import render_product_login_page


def test_login_presenter_has_two_step_otp_flow_without_provider_tokens():
    html = render_product_login_page()

    assert 'id="email-step"' in html
    assert 'id="code-step"' in html
    assert 'autocomplete="one-time-code"' in html
    assert "fetch(url" in html
    assert 'post("/auth/otp/request"' in html
    assert 'post("/auth/otp/verify"' in html
    assert "access_token" not in html
    assert "refresh_token" not in html
    assert "SUPABASE" not in html
