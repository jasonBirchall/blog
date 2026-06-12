output "server_ipv4" {
  description = "Public IPv4 of the VPS (for the Gandi apex A record and the Hetzner console)."
  value       = hcloud_server.blog.ipv4_address
}

output "server_ipv6" {
  description = "Public IPv6 of the VPS."
  value       = hcloud_server.blog.ipv6_address
}

output "bucket_name" {
  description = "Object Storage bucket holding Litestream replicas and tofu state."
  value       = aws_s3_bucket.data.bucket
}
