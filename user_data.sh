#!/bin/bash
# Everything here runs as root at first boot.
# It authenticates with the INSTANCE ROLE - there are no keys in this file.
exec > /var/log/user-data.log 2>&1
set -x

BUCKET="__BUCKET__"
TABLE="__TABLE__"
REGION="__REGION__"
IMAGE_KEY="__IMAGE_KEY__"
IMAGE_ID="__IMAGE_ID__"

# Amazon Linux 2023 already has the AWS CLI; we only need a web server.
dnf install -y nginx
WEBROOT=/usr/share/nginx/html
mkdir -p "$WEBROOT"

# --- 1. download the image from S3 -----------------------------------
aws s3 cp "s3://$BUCKET/$IMAGE_KEY" "$WEBROOT/$IMAGE_ID" --region "$REGION"

# --- 2. read its metadata from DynamoDB ------------------------------
KEYJSON="{\"image_id\":{\"S\":\"$IMAGE_ID\"}}"
get_attr () {
  aws dynamodb get-item --table-name "$TABLE" --region "$REGION" \
      --key "$KEYJSON" --query "Item.$1" --output text 2>/dev/null
}
SIZE=$(get_attr 'file_size_bytes.N')
CTYPE=$(get_attr 'content_type.S')
UPLOADED=$(get_attr 'uploaded_at.S')
OWNER=$(get_attr 'uploaded_by.S')

# --- 3. who am I? ----------------------------------------------------
TOKEN=$(curl -sX PUT "http://169.254.169.254/latest/api/token" \
        -H "X-aws-ec2-metadata-token-ttl-seconds: 300")
MD="http://169.254.169.254/latest/meta-data"
IID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" $MD/instance-id)
AZ=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
     $MD/placement/availability-zone)

# --- 4. build the page -----------------------------------------------
cat > "$WEBROOT/index.html" <<HTML
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Image Gallery - $OWNER</title>
<style>
  :root { color-scheme: light dark; }
  body { margin:0; font-family: system-ui, Segoe UI, Roboto, sans-serif;
         background:#232F3E; color:#E6EDF3; }
  .wrap { max-width: 860px; margin: 0 auto; padding: 40px 20px; }
  h1 { font-size: 28px; margin: 0 0 6px; }
  .sub { color:#9AA5B1; margin: 0 0 28px; font-size: 15px; }
  .card { background:#2F3E52; border-radius: 10px; overflow:hidden; }
  img { display:block; width:100%; height:auto; background:#1A222E; }
  table { width:100%; border-collapse: collapse; font-size: 14px; }
  td { padding: 10px 18px; border-top: 1px solid #3C4C61; }
  td:first-child { color:#9AA5B1; width: 190px; }
  .tag { display:inline-block; background:#FF9900; color:#232F3E;
         font-weight:700; font-size:12px; padding:3px 9px;
         border-radius: 999px; }
  footer { color:#6F7D8C; font-size:12px; margin-top:22px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Image Gallery</h1>
  <p class="sub">Served from EC2 &middot; image stored in S3 &middot;
     metadata in DynamoDB</p>

  <div class="card">
    <img src="$IMAGE_ID" alt="$IMAGE_ID">
    <table>
      <tr><td>File name</td><td>$IMAGE_ID</td></tr>
      <tr><td>S3 location</td><td>s3://$BUCKET/$IMAGE_KEY</td></tr>
      <tr><td>Size</td><td>$SIZE bytes</td></tr>
      <tr><td>Content type</td><td>$CTYPE</td></tr>
      <tr><td>Uploaded by</td><td>$OWNER</td></tr>
      <tr><td>Uploaded at</td><td>$UPLOADED</td></tr>
      <tr><td>DynamoDB table</td><td>$TABLE</td></tr>
      <tr><td>Served by</td><td>$IID in $AZ</td></tr>
      <tr><td>Status</td><td><span class="tag">DISPLAYED</span></td></tr>
    </table>
  </div>

  <footer>This server holds no AWS credentials. It reads S3 and DynamoDB
  using the IAM role attached through LabInstanceProfile.</footer>
</div>
</body>
</html>
HTML

# --- 5. mark the record as displayed ---------------------------------
# 'status' is a DynamoDB reserved word, so it must be aliased with #s.
aws dynamodb update-item --table-name "$TABLE" --region "$REGION" \
  --key "$KEYJSON" \
  --update-expression "SET #s = :s, served_by = :i, served_at = :t" \
  --expression-attribute-names '{"#s":"status"}' \
  --expression-attribute-values "{
      \":s\":{\"S\":\"DISPLAYED\"},
      \":i\":{\"S\":\"$IID\"},
      \":t\":{\"S\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}}"

# --- 6. start the web server -----------------------------------------
systemctl enable --now nginx
echo "USER DATA COMPLETE"
