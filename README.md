# frontal  
**QVOES Project Backend Test Task**

This Readme provides instructions for setting up and running the full system for the Frontal API Services.

### How to Run the Full System:

To set up and run the system, follow these steps:

1. **Start the PostgreSQL Services:**

   Navigate to the `databases` directory and launch the PostgreSQL services using Docker Compose. This will start the necessary database containers in the background.

   ```bash
   cd databases
   docker-compose up -d

Note: Ensure Docker and Docker Compose are installed and running on your system.

2. **Grant Execution Permissions to Shell Scripts:**
    Navigate to the server directory and provide executable permissions to the following scripts: active.sh, deactivate.sh, and install.sh.

    cd ../server
    chmod a+x active.sh deactivate.sh install.sh

Note: These scripts are essential for activating and installing necessary components of the backend service.

3. **Run the active.sh and install.sh Scripts:**
    First, execute active.sh to activate the necessary services or configurations. Then, run install.sh to install any required dependencies and set up the environment.

    sh active.sh
    sh install.sh

Note: These scripts must be run in sequence for proper initialization and setup of the backend.

4. **Grant Execution Permissions and Start the API Service:**
    Navigate to the api directory and provide executable permissions to the startAPIService.sh script. This script will start the API service for the project.

    cd api
    chmod a+x startAPIService.sh
    sh startAPIService.sh

Note: Ensure the system's environment variables and configurations are properly set before starting the API service.

**Troubleshooting:**
If you encounter any issues during these steps, please check the logs for errors.
Ensure that all dependencies are installed and that the PostgreSQL container is running.
You may need to restart services if the system does not behave as expected.

**Additional Notes:**
Ensure that all necessary environment variables (such as database credentials) are set up correctly before running the scripts.
If you make any modifications to the database or backend, be sure to restart the relevant services to apply changes.

**Dependencies:**
Docker & Docker Compose: For managing containers and services.
PostgreSQL: The relational database management system used by the project.
Shell Scripts: The project requires several shell scripts for activation, installation, and service management.

Tip: If you experience any slow performance, consider checking your system’s resource usage, as Docker containers may consume significant CPU/RAM resources.