from thefuzz import process

test = {563372552643149825: [{'name': 'test', 'content': 'test'}, {'name': 'test1', 'content': 'test'}]}

matches = process.extract('test1', [tag['name'] for tag in test[563372552643149825]], limit=10)
print(matches)