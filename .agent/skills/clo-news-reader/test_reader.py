import pytest
from reader import CLONewsReader

def test_fetch_news_no_query():
    reader = CLONewsReader()
    news = reader.fetch_news()
    assert len(news) > 0
    assert "title" in news[0]
    assert "source" in news[0]

def test_fetch_news_with_query():
    reader = CLONewsReader()
    news = reader.fetch_news(query="Ares")
    assert len(news) == 1
    assert "Ares" in news[0]["title"]

def test_fetch_news_limit():
    reader = CLONewsReader()
    news = reader.fetch_news(limit=2)
    assert len(news) == 2

def test_fetch_news_no_results():
    reader = CLONewsReader()
    news = reader.fetch_news(query="NonExistentKeyword")
    assert len(news) == 0
