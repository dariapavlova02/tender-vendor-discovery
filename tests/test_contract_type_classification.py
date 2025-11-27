import pytest
from vendor_ai_agent.modules.tender_profiler import TenderProfiler
from vendor_ai_agent.modules.llm_providers import OpenAIProvider
from vendor_ai_agent.config import LLMConfig


class TestContractTypeClassification:
    
    @pytest.fixture
    def profiler(self):
        llm_config = LLMConfig()
        llm_provider = OpenAIProvider(
            default_model=llm_config.smart_model,
            use_flex_tier=llm_config.use_flex_tier
        )
        return TenderProfiler(llm_provider=llm_provider)
    
    def test_service_contract_grounds_maintenance(self, profiler):
        scope_text = """
        The City of Waterloo requires grounds maintenance services for all municipal properties.
        Contractor shall provide: lawn mowing, tree trimming, snow removal, fertilizer application,
        and irrigation system maintenance. Contractor must supply all equipment, materials, and labor.
        Materials include fertilizer, salt for de-icing, mulch, and replacement plants.
        """
        
        context = profiler.generate_context_from_text(scope_text)
        
        print(f"\n=== SERVICE CONTRACT TEST ===")
        print(f"Contract Type: {context.contract_type} (confidence: {context.contract_type_confidence})")
        print(f"Fulfillment Model: {context.fulfillment_model}")
        print(f"Primary Deliverables: {context.primary_deliverables}")
        print(f"Vendor Inputs: {context.vendor_inputs}")
        print(f"Search Terms ({len(context.search_terms)}): {context.search_terms[:5]}")
        
        assert context.contract_type == "service"
        assert context.contract_type_confidence >= 0.75
        assert context.fulfillment_model == "contractor"
        
        deliverables_str = " ".join([d.lower() for d in context.primary_deliverables])
        assert "grounds maintenance" in deliverables_str or "lawn" in deliverables_str
        
        inputs_str = " ".join([i.lower() for i in context.vendor_inputs])
        assert "fertilizer" in inputs_str or "salt" in inputs_str or "mulch" in inputs_str
        
        # Check that vendor inputs are NOT in search terms
        for term in context.search_terms:
            term_lower = term.lower()
            assert "fertilizer supplier" not in term_lower
            assert "salt supplier" not in term_lower
            assert "mulch distributor" not in term_lower
    
    def test_product_contract_office_furniture(self, profiler):
        scope_text = """
        The Government of Canada requires 200 ergonomic office chairs and 50 adjustable desks.
        Products must meet CSA standards. Delivery FOB destination. Installation by buyer's staff.
        Items must include: lumbar support, adjustable armrests, and 5-year warranty.
        """
        
        context = profiler.generate_context_from_text(scope_text)
        
        print(f"\n=== PRODUCT CONTRACT TEST ===")
        print(f"Contract Type: {context.contract_type} (confidence: {context.contract_type_confidence})")
        print(f"Fulfillment Model: {context.fulfillment_model}")
        print(f"Search Terms ({len(context.search_terms)}): {context.search_terms[:5]}")
        
        assert context.contract_type == "product"
        assert context.contract_type_confidence >= 0.75
        assert context.fulfillment_model in ["manufacturer", "distributor"]
        assert any("chair" in d.lower() or "desk" in d.lower() for d in context.primary_deliverables)
    
    def test_hybrid_contract_hvac_system(self, profiler):
        scope_text = """
        Supply and install a complete HVAC system for new municipal facility. 
        Contractor shall provide: rooftop units, ductwork, controls, and installation services.
        System must be commissioned and tested. Training for maintenance staff required.
        """
        
        context = profiler.generate_context_from_text(scope_text)
        
        assert context.contract_type == "hybrid"
        assert context.contract_type_confidence >= 0.75
        assert context.fulfillment_model == "integrator"
        
        search_terms_str = " ".join(context.search_terms).lower()
        assert "turnkey" in search_terms_str or "installation" in search_terms_str
    
    def test_consulting_contract_it_advisory(self, profiler):
        scope_text = """
        The agency requires cybersecurity assessment and strategic advisory services.
        Consultant shall: conduct vulnerability assessment, develop security roadmap,
        provide staff training on security best practices. Deliverables include assessment
        report, implementation plan, and training materials.
        """
        
        context = profiler.generate_context_from_text(scope_text)
        
        print(f"\n=== CONSULTING CONTRACT TEST ===")
        print(f"Contract Type: {context.contract_type} (confidence: {context.contract_type_confidence})")
        print(f"Fulfillment Model: {context.fulfillment_model}")
        print(f"Search Terms ({len(context.search_terms)}): {context.search_terms[:5]}")
        
        assert context.contract_type == "consulting"
        assert context.contract_type_confidence >= 0.75
        assert context.fulfillment_model == "consultant"
    
    def test_safety_rails_filter_vendor_inputs(self, profiler):
        scope_text = """
        Landscaping services for government campus. Contractor provides: lawn care, tree maintenance,
        seasonal plantings. Contractor must supply: commercial mowers, fertilizer, mulch, plants.
        """
        
        context = profiler.generate_context_from_text(scope_text)
        
        filtered_terms = profiler._validate_and_filter_search_terms(
            context.search_terms,
            contract_type=context.contract_type,
            contract_type_confidence=context.contract_type_confidence or 0.8,
            vendor_inputs=context.vendor_inputs
        )
        
        filtered_str = " ".join(filtered_terms).lower()
        assert "fertilizer supplier" not in filtered_str
        assert "mulch distributor" not in filtered_str
        assert "mower manufacturer" not in filtered_str
    
    def test_contract_type_distribution_compliance(self, profiler):
        test_cases = [
            ("service", "Janitorial cleaning services for office buildings", "contractor"),
            ("product", "Purchase 100 laptops Dell Latitude series", "manufacturer"),
            ("hybrid", "Supply and install security camera system", "integrator"),
        ]
        
        for expected_type, scope, expected_fulfillment in test_cases:
            context = profiler.generate_context_from_text(scope)
            
            if context.contract_type_confidence and context.contract_type_confidence >= 0.75:
                assert context.contract_type == expected_type, \
                    f"Expected {expected_type}, got {context.contract_type} for: {scope[:50]}"
                
                contractor_terms = sum(1 for term in context.search_terms 
                                      if any(kw in term.lower() for kw in ["contractor", "service provider"]))
                manufacturer_terms = sum(1 for term in context.search_terms 
                                        if any(kw in term.lower() for kw in ["manufacturer", "producer", "oem"]))
                
                if expected_type == "service":
                    assert contractor_terms > manufacturer_terms
                elif expected_type == "product":
                    assert manufacturer_terms > contractor_terms
