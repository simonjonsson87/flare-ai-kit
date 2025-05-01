
# backend/main.py
"""
AI Agent API Main Application Module

This module initializes and configures the FastAPI application for the AI Agent API.
It sets up CORS middleware, integrates various providers (AI, blockchain, attestation),
and configures the chat routing system.

Dependencies:
    - FastAPI for the web framework
    - Structlog for structured logging
    - CORS middleware for cross-origin resource sharing
    - Custom providers for AI, blockchain, and attestation services
"""
import os, tempfile
import structlog
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import ssl # For ssl.CERT_NONE

#from flare_ai_kit.tee import create_ssl_context
from flare_ai_kit.tee import generate_self_signed_cert
import uvicorn
from uvicorn.config import Config
from uvicorn.server import Server
import asyncio

from .chat import ChatRouter
from flare_ai_kit.tee.attestation import VtpmAttestation



from settings import settings

logger = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application instance.

    This function:
    1. Creates a new FastAPI instance
    2. Configures CORS middleware with settings from the configuration
    3. Initializes required service providers:
       - GeminiProvider for AI capabilities
       - FlareProvider for blockchain interactions
       - Vtpm for attestation services
       - PromptService for managing chat prompts
    4. Sets up routing for chat endpoints

    Returns:
        FastAPI: Configured FastAPI application instance

    Configuration:
        The following settings are used from settings module:
        - api_version: API version string
        - cors_origins: List of allowed CORS origins
        - gemini_api_key: API key for Gemini AI service
        - gemini_model: Model identifier for Gemini AI
        - web3_provider_url: URL for Web3 provider
        - simulate_attestation: Boolean flag for attestation simulation
    """
    app = FastAPI(
        title="AI Agent API", version=settings.api_version, redirect_slashes=False
    )

    # Configure CORS middleware with settings from configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize router with service providers
    chat = ChatRouter(
        #ai=GeminiProvider(api_key=settings.gemini_api_key, model=settings.gemini_model),
        #blockchain=FlareProvider(web3_provider_url=settings.web3_provider_url),
        attestation=VtpmAttestation(simulate=settings.simulate_attestation)
        #prompts=PromptService(),
    )

    # Register chat routes with API
    app.include_router(chat.router, prefix="/api/routes/chat", tags=["chat"])
    
    return app


app = create_app()


def start() -> None:
    """
    Start the FastAPI application server using uvicorn with RA-TLS and an in-memory certificate.

    This function:
    1. Initializes the attestation provider.
    2. Creates an in-memory SSLContext with a self-signed certificate and attestation token.
    3. Writes the certificate and key to temporary files for Uvicorn.
    4. Runs uvicorn with the temporary certificate and key files.
    """
    # Initialize attestation
    attestation = VtpmAttestation(simulate=settings.simulate_attestation)
    
    # Generate attestation token
    token = attestation.get_token([])  # Adjust if specific input is needed

    # Create SSL context with attestation token
    key_pem, cert_pem = generate_self_signed_cert(token, common_name="localhost", days_valid=365)

    cert_dir = "/app/certs"
    os.makedirs(cert_dir, exist_ok=True)
    cert_path = os.path.join(cert_dir, "server_cert.pem")
    abs_cert_path = os.path.abspath(cert_path)
    with open(cert_path, "wb") as f:
        f.write(cert_pem)
    logger.info(f"Saved certificate to {cert_path} (absolute: {abs_cert_path})")

    # Create temporary files for certificate and key
    cert_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    key_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    try:
        cert_file.write(cert_pem)
        cert_file.flush()
        key_file.write(key_pem)
        key_file.flush()

        # Run Uvicorn with temporary certificate and key files
        uvicorn.run(
            app=app,
            host="0.0.0.0",
            port=8080,
            ssl_certfile=cert_file.name,
            ssl_keyfile=key_file.name,
            ssl_cert_reqs=ssl.CERT_NONE,  # No client certificate verification
            ssl_ciphers="TLSv1.2,TLSv1.3",  # Support both TLSv1.2 and TLSv1.3 for compatibility
            loop="auto",
            http="auto",
            workers=1,
            log_level="debug",
            access_log=True
        )
    finally:
        # Clean up temporary files
        cert_file.close()
        key_file.close()
        os.unlink(cert_file.name)
        os.unlink(key_file.name)
        
if __name__ == "__main__":
    #asyncio.run(start())
    start()

