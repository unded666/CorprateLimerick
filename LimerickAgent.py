from google.adk.agents import Agent, SequentialAgent
from google.adk.runners import InMemoryRunner
from google.adk.tools import google_search
import asyncio

def create_agents():

    research_agent = Agent(
        model="gemini-2.5-flash",
        name="research_agent",
        description="Researches the performance of a given company",
        instruction="""You are a specialised company research agent.
    
        Given the name of a publicly traded company, research its performance over the last
        three years, paying particular attention to dividends paid out, the market cap, the share price and the P/E ratio.
    
        The results are to be returned in a bullet-point summary. No additional commentary is required.""",
        tools=[google_search]
    )

    limerick_agent = Agent(
        model="gemini-2.5-flash",
        name="limerick_agent",
        description="Writes a limerick about a given topic",
        instruction="""You are a creative limerick writing agent.   
        Given the company research summary, write a limerick that captures the key points in a humorous way.
        The limerick should follow the traditional AABBA rhyme scheme and be light-hearted and fun.""",
    )

    root_agent = SequentialAgent(
        name="root_agent",
        description="Agent that researches a company and writes a limerick about it",
        sub_agents=[research_agent, limerick_agent],
    )

    out_dict = {
        "research_agent": research_agent,
        "limerick_agent": limerick_agent,
        "root_agent": root_agent
    }
    return out_dict

def run_limerick_agent(input_company: str) -> str:
    """Run the limerick agent for a given company and return the generated limerick."""
    agent_dict = create_agents()

    # Create the runner with the root agent and set app_name to match the agent's origin
    runner = InMemoryRunner(agent=agent_dict['root_agent'], app_name="agents")

    async def _run_and_collect(prompt: str):
        """Run the agent and ensure the runner is closed afterward to avoid memory bloat."""
        try:
            events = await runner.run_debug(prompt, quiet=True)
            return events
        finally:
            # Close the runner to release in-memory resources (tools, sessions, etc.).
            # Runner.close() is async, so we await it here.
            await runner.close()

    events = asyncio.run(_run_and_collect(input_company))

    # Gather all text parts produced by the agent and return only the final non-empty text (the limerick)
    text_parts = []
    for event in events:
        if getattr(event, "content", None) and getattr(event.content, "parts", None):
            for part in event.content.parts:
                if getattr(part, "text", None):
                    text = part.text.strip()
                    if text:
                        text_parts.append(text)

    if text_parts:
        # Return only the last text produced (assumed to be the final limerick)
        return text_parts[-1]
    return ""


if __name__ == "__main__":
    prompt = "Cadburys"  # initial prompt
    # events = asyncio.run(_run_and_collect(prompt))
    output_limerick = run_limerick_agent(prompt)
    print(output_limerick)
