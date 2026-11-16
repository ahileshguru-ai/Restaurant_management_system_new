import bcrypt

passwords = {
    'shopmanager': 'manager123',
    'kitchenmgr': 'kitchen123',
    'chef_vikram': 'chef123',
    'chef_meera': 'chef123',
    'waiter_rahul': 'waiter123',
    'waiter_priya': 'waiter123',
}

hashes = {}
for user, pw in passwords.items():
    h = bcrypt.hashpw(pw.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')
    assert bcrypt.checkpw(pw.encode('utf-8'), h.encode('utf-8'))
    hashes[user] = (pw, h)
    print(f"'{user}': ('{pw}', '{h}'),")
