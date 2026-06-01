import pytest
from agents.news_reader.reader import CLONewsReader

def test_fetch_news_no_query():
    reader = CLONewsReader()
    news = reader.fetch_news()
    assert len(news) > 0
    assert "title" in news[0]
    assert "source" in news[0]

def test_fetch_news_with_query():
    reader = CLONewsReader()
    news = reader.fetch_news(query="CLO", limit=1)
    assert len(news) > 0
    # Search results might have titles formatted differently, but should be relevant
    assert "CLO" in news[0]["title"].upper() or "CLO" in news[0]["summary"].upper()

def test_fetch_news_limit():
    reader = CLONewsReader()
    news = reader.fetch_news(limit=2)
    assert len(news) <= 2

def test_fetch_news_no_results():
    reader = CLONewsReader()
    # Use a very obscure string to ensure no results
    news = reader.fetch_news(query="ZXYWVUTSRQPONMLKJIHGFEDCBA", limit=1)
    assert len(news) == 0
