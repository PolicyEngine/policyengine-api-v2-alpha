#!/bin/bash
# Get the current public IP of the API ECS task

set -e

CLUSTER_NAME=${1:-policyengine-api-v2-alpha}
SERVICE_NAME=${2:-policyengine-api-v2-alpha-api}
AWS_REGION=${3:-us-east-1}

echo "Getting API endpoint for cluster: $CLUSTER_NAME, service: $SERVICE_NAME"

TASK_ARN=$(aws ecs list-tasks \
  --cluster "$CLUSTER_NAME" \
  --service-name "$SERVICE_NAME" \
  --region "$AWS_REGION" \
  --desired-status RUNNING \
  --query 'taskArns[0]' \
  --output text)

if [ -z "$TASK_ARN" ] || [ "$TASK_ARN" == "None" ]; then
  echo "Error: No running tasks found"
  exit 1
fi

NETWORK_INTERFACE_ID=$(aws ecs describe-tasks \
  --cluster "$CLUSTER_NAME" \
  --tasks "$TASK_ARN" \
  --region "$AWS_REGION" \
  --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' \
  --output text)

PUBLIC_IP=$(aws ec2 describe-network-interfaces \
  --network-interface-ids "$NETWORK_INTERFACE_ID" \
  --region "$AWS_REGION" \
  --query 'NetworkInterfaces[0].Association.PublicIp' \
  --output text)

if [ -z "$PUBLIC_IP" ] || [ "$PUBLIC_IP" == "None" ]; then
  echo "Error: Could not retrieve public IP"
  exit 1
fi

echo ""
echo "API endpoint: http://$PUBLIC_IP"
echo "Health check: http://$PUBLIC_IP/health"
echo "Documentation: http://$PUBLIC_IP/docs"
echo ""
echo "IP address: $PUBLIC_IP"
