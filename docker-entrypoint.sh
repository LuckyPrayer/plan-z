#!/bin/bash
# Plan-Z Docker Entrypoint
# Handles docker socket permissions and starts the application

set -e

# If docker socket exists, ensure the user can access it
if [ -S /var/run/docker.sock ]; then
    # Get the GID of the docker socket
    SOCKET_GID=$(stat -c '%g' /var/run/docker.sock)
    
    # Check if a group with this GID exists
    if ! getent group "$SOCKET_GID" > /dev/null 2>&1; then
        # Create a group with the socket's GID
        groupadd -g "$SOCKET_GID" dockerhost 2>/dev/null || true
    fi
    
    # Get the group name for this GID
    DOCKER_GROUP=$(getent group "$SOCKET_GID" | cut -d: -f1)
    
    # Add planz user to this group if not already a member
    if ! id -nG planz | grep -qw "$DOCKER_GROUP"; then
        usermod -aG "$DOCKER_GROUP" planz 2>/dev/null || true
    fi
fi

# If running as root, switch to planz user
if [ "$(id -u)" = "0" ]; then
    exec gosu planz "$@"
else
    exec "$@"
fi
