import bcrypt

valid_hashes = {
    'shopmanager': '$2b$12$emFziUmmHFcmpJcofB9bFuzIQqqEpYXfnLU4IjeEJXI6Lbi0TbZ9S',
    'kitchenmgr': '$2b$12$Sz1Pm5Q/Mb4DEDNCokgWYew14ZS0OH.Cw6W9zLKcoYoO/dEfBK8s6',
    'chef_vikram': '$2b$12$AcxMwlXLVtzkmprY2zufOONmJCxN97lqr1NZEhTZmDB0ZnHDxUZ1q',
    'chef_meera': '$2b$12$mZX8tFTbik.Gk.4ndvfswOAeuMnuWmrVj11.RrWWAZtqJsTF6NyJm',
    'waiter_rahul': '$2b$12$DI1Hu.HyGCvJpp/7k72UKOAdsNF7shokinRHO0d4XYSxyTxFW3Sr6',
    'waiter_priya': '$2b$12$nH47gatl/jgxL.uuN0Cg8u5Urxm3DMdkJjDGxhWE9vxrQLsdoOBSe',
}

passwords = {
    'shopmanager': 'manager123',
    'kitchenmgr': 'kitchen123',
    'chef_vikram': 'chef123',
    'chef_meera': 'chef123',
    'waiter_rahul': 'waiter123',
    'waiter_priya': 'waiter123',
}

for uname, expected_pw in passwords.items():
    h = valid_hashes[uname]
    ok = bcrypt.checkpw(expected_pw.encode('utf-8'), h.encode('utf-8'))
    print(f"{uname} ({expected_pw}): {ok}")
    assert ok is True

print("All 6 demo accounts verified 100% successfully!")
