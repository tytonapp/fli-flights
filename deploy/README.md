# Deploying to appsstore.io/searchflights

Assumes the Hostinger VPS (Ubuntu + nginx) that already serves appsstore.io.
Run these on the VPS over SSH.

## 1. Install the app

```bash
sudo apt install -y python3-venv git
sudo git clone https://github.com/tytonapp/fli-flights.git /var/www/fli-flights
cd /var/www/fli-flights
sudo python3 -m venv venv
sudo venv/bin/pip install -r requirements.txt
sudo chown -R www-data:www-data /var/www/fli-flights
```

Check that the server can reach Google Flights:

```bash
sudo -u www-data venv/bin/python check.py    # should print "results: <number>"
```

## 2. Run it as a service

```bash
sudo cp deploy/searchflights.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now searchflights
curl -s http://127.0.0.1:5001/ | head -3     # should print the page's HTML
```

Port 5001 must be free (`sudo ss -ltnp | grep 5001`). If it isn't, change it in both
`searchflights.service` and `nginx-searchflights.conf`.

## 3. Add it to nginx

The appsstore.io server block includes every file in `/etc/nginx/appsstore-apps/`,
so each app gets its own file and the main config is never edited:

```bash
sudo cp deploy/nginx-searchflights.conf /etc/nginx/appsstore-apps/searchflights.conf
sudo nginx -t && sudo systemctl reload nginx
```

Open https://appsstore.io/searchflights/

## Updating

```bash
cd /var/www/fli-flights
sudo -u www-data git pull
sudo -u www-data venv/bin/pip install -r requirements.txt
sudo systemctl restart searchflights
```

Logs: `sudo journalctl -u searchflights -f`

## Optional: list it on the home page

Add a line to the `<ul>` in the appsstore.io home page `index.html`:

```html
<li><a href="/searchflights/">Search Flights - live Google Flights fares</a></li>
```
