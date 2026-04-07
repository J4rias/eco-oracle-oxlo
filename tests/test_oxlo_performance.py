import time
import logging
import sys
import os

# Add parent dir to sys.path to import our services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.oxlo_client import OxloReasoningClient
from core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("oxlo_test")

def benchmark_reasoning():
    if not settings.oxlo_configured:
        logger.error("OXLO_API_KEY not configured. Cannot run benchmark.")
        return

    client = OxloReasoningClient()
    
    # A typical complex prompt that caused delays
    test_prompt = """
    ## EUDR Compliance Analysis Request
    ### Farm Details
    - Crop type: Coffee
    - Reported volume: 50.0 metric tons
    - Polygon area: 122.96 ha
    
    ### Vision Analysis Summary
    {"deforestation_detected": true, "earliest_deforestation_date": "2024-04-12", "max_confidence": 0.88}
    
    ### Relevant EUDR Regulation Excerpts (RAG)
    • Article 3.1: Relevant commodities and relevant products shall not be placed or made available on the market unless they are deforestation-free.
    • Article 2.13: 'deforestation-free' means that the relevant commodities and relevant products were produced on land that has not been subject to deforestation after 31 December 2020.
    
    Provide a detailed legal rationale.
    """
    
    system_prompt = "You are an expert EUDR compliance officer. Reason strictly based on Regulation (EU) 2023/1115."
    
    logger.info("Sending complex reasoning request to Oxlo (DeepSeek R1)...")
    start_time = time.time()
    
    try:
        response = client.reason(prompt=test_prompt, system_prompt=system_prompt)
        duration = time.time() - start_time
        
        logger.info(f"✅ Success! Response received in {duration:.2f} seconds.")
        logger.info(f"Response length: {len(response)} characters")
        print("\n--- RESPONSE PREVIEW ---\n")
        print(response[:500] + "...")
        
        if duration > 60:
            logger.warning("⏱️ Request took > 60s. This would have timed out under old settings.")
        else:
            logger.info("⏱️ Request within standard 60s window.")

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"❌ Failed after {duration:.2f} seconds: {e}")

if __name__ == "__main__":
    benchmark_reasoning()
