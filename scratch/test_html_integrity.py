import os
import re

def test_html():
    html_path = os.path.join("static", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    print("--- Checking HTML for removed prototype elements ---")
    assert "demoProfileSelect" not in html, "Found demoProfileSelect in HTML!"
    assert "viewport-pill" not in html, "Found viewport-pill in HTML!"
    assert "🔑 Sign In" not in html, "Found prototype Sign In button in HTML!"
    assert "🔄 Reset DB" not in html, "Found Reset DB button in HTML!"
    print("[OK] All prototype switching controls successfully removed.")

    print("\n--- Checking HTML for 4-Role Login Portal ---")
    assert 'id="loginPortal"' in html, "Missing #loginPortal!"
    assert 'id="roleSelectionGrid"' in html, "Missing #roleSelectionGrid!"
    assert "Shop Manager" in html, "Missing Shop Manager card!"
    assert "Kitchen Manager" in html, "Missing Kitchen Manager card!"
    assert "Chef" in html, "Missing Chef card!"
    assert "Waiter" in html, "Missing Waiter card!"
    assert 'id="roleCredentialBox"' in html, "Missing #roleCredentialBox!"
    assert 'id="portalUsername"' in html, "Missing #portalUsername!"
    assert 'id="portalPassword"' in html, "Missing #portalPassword!"
    assert 'App.submitPortalLogin()' in html, "Missing submitPortalLogin call!"
    assert 'App.backToRoleSelection()' in html, "Missing backToRoleSelection call!"
    print("[OK] 4-Role Login Portal structure verified.")

    print("\n--- Checking Clean Topbar & Sign Out ---")
    assert 'App.logout()' in html, "Missing App.logout() trigger!"
    assert "Sign Out" in html, "Missing Sign Out button!"
    assert 'id="topUserDisplayName"' in html, "Missing #topUserDisplayName!"
    assert 'id="topUserRoleBadge"' in html, "Missing #topUserRoleBadge!"
    print("[OK] Topbar user session and Sign Out button verified.")

    print("\n--- Checking Shop Manager Personnel Administration ---")
    assert 'App.openRegisterUserModal()' in html, "Missing openRegisterUserModal in Shop Manager!"
    assert '+ Register Staff Member' in html, "Missing + Register Staff Member button!"
    assert 'App.submitRegisterUser()' in html, "Missing submitRegisterUser!"
    assert 'App.submitUpdateCredentials()' in html, "Missing submitUpdateCredentials!"
    print("[OK] Shop Manager personnel and credential editing administration verified.")

    print("\nALL HTML INTEGRITY CHECKS PASSED!")

if __name__ == "__main__":
    test_html()
