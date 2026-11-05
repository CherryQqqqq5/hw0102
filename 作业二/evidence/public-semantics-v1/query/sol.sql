WITH statistics AS (
SELECT w.wordid, w.word, COUNT(DISTINCT s.synsetid) AS total_synsets,
COUNT(*) AS total_senses, COUNT(DISTINCT syn.domainid) AS distinct_domains,
COUNT(DISTINCT syn.posid) AS distinct_posids
FROM words w JOIN senses s ON w.wordid=s.wordid
JOIN synsets syn ON s.synsetid=syn.synsetid
GROUP BY w.wordid,w.word
HAVING total_synsets>=2 AND distinct_domains>=2 AND total_senses>=2
), counts AS (
SELECT wordid,synsetid,COUNT(*) AS n FROM senses GROUP BY wordid,synsetid
), ranked AS (
SELECT wordid,synsetid,n,ROW_NUMBER() OVER (PARTITION BY wordid ORDER BY n DESC,synsetid ASC) AS position
FROM counts
)
SELECT a.wordid AS word_id,a.word,a.total_synsets,a.total_senses,
a.distinct_domains,a.distinct_posids,b.synsetid AS top_synsetid,b.n AS top_synset_sense_count
FROM statistics a JOIN ranked b ON a.wordid=b.wordid AND b.position=1
ORDER BY total_senses DESC,total_synsets DESC,distinct_domains DESC,word_id ASC LIMIT 500;
