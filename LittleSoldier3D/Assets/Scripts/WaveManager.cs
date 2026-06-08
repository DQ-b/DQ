using System.Collections;
using UnityEngine;
using UnityEngine.AI;

[System.Serializable]
public class Wave
{
    public int enemyCount = 3;
    public float enemyHealth = 45f;
    public float enemyMoveSpeed = 3.5f;
    public float enemyAttackDamage = 8f;
}

public class WaveManager : MonoBehaviour
{
    public static WaveManager Instance;

    public Wave[] waves;
    public Transform[] spawnPoints;
    public float startDelay = 4f;
    public float interWaveDelay = 4f;
    public float spawnInterval = 1.6f;

    [Header("Phase 6 AI")]
    public Transform[] patrolPoints;
    public Transform[] coverPoints;
    public EnemyAI.Difficulty difficulty = EnemyAI.Difficulty.Normal;

    public int CurrentWave { get; private set; }
    public int TotalWaves { get { return waves != null ? waves.Length : 0; } }

    public string BannerText { get; private set; } = "";
    public float BannerUntil { get; private set; } = 0f;

    void Awake()
    {
        Instance = this;
    }

    void Start()
    {
        int totalEnemies = 0;
        if (waves != null)
        {
            foreach (Wave wave in waves)
                totalEnemies += wave.enemyCount;
        }

        if (GameManager.Instance != null && totalEnemies > 0)
            GameManager.Instance.killsToWin = totalEnemies;

        StartCoroutine(RunWaves());
    }

    private IEnumerator RunWaves()
    {
        yield return new WaitForSeconds(startDelay);

        for (int i = 0; i < waves.Length; i++)
        {
            CurrentWave = i + 1;
            ShowBanner("\u7b2c " + CurrentWave + " \u6ce2\u5f00\u59cb!", 2.5f);
            yield return StartCoroutine(SpawnWave(waves[i]));

            yield return new WaitUntil(() => CountEnemies() == 0);

            if (i < waves.Length - 1)
            {
                ShowBanner("\u672c\u6ce2\u6e05\u9664, \u51c6\u5907\u4e0b\u4e00\u6ce2!", interWaveDelay);
                yield return new WaitForSeconds(interWaveDelay);
            }
        }
    }

    private IEnumerator SpawnWave(Wave wave)
    {
        for (int i = 0; i < wave.enemyCount; i++)
        {
            SpawnEnemy(wave);
            yield return new WaitForSeconds(spawnInterval);
        }
    }

    private void SpawnEnemy(Wave wave)
    {
        Vector3 position = GetSpawnPos();

        GameObject enemy = GameObject.CreatePrimitive(PrimitiveType.Capsule);
        enemy.name = "Enemy";
        enemy.transform.position = position;

        Renderer renderer = enemy.GetComponent<Renderer>();
        if (renderer != null)
        {
            Material material = renderer.material;
            Color color = EnemyColor(wave);
            if (material.HasProperty("_Color"))
                material.SetColor("_Color", color);
            if (material.HasProperty("_BaseColor"))
                material.SetColor("_BaseColor", color);
        }

        NavMeshAgent agent = enemy.AddComponent<NavMeshAgent>();
        agent.radius = 0.5f;
        agent.height = 2f;
        agent.speed = wave.enemyMoveSpeed * SpeedMult();
        agent.angularSpeed = 720f;
        agent.acceleration = 24f;
        agent.stoppingDistance = 0.5f;

        EnemyHealth health = enemy.AddComponent<EnemyHealth>();
        health.health = wave.enemyHealth * HealthMult();

        EnemyAI ai = enemy.AddComponent<EnemyAI>();
        ai.attackDamage = wave.enemyAttackDamage;
        ai.difficulty = difficulty;
        ai.patrolPoints = patrolPoints;
        ai.coverPoints = coverPoints;
        ai.spawnAwarenessDelay = 2.5f + CurrentWave * 0.5f;

        if (NavMesh.SamplePosition(position, out NavMeshHit hit, 4f, NavMesh.AllAreas))
            agent.Warp(hit.position);
    }

    private float HealthMult()
    {
        if (difficulty == EnemyAI.Difficulty.Easy)
            return 0.8f;
        if (difficulty == EnemyAI.Difficulty.Hard)
            return 1.3f;
        return 1f;
    }

    private float SpeedMult()
    {
        if (difficulty == EnemyAI.Difficulty.Easy)
            return 0.9f;
        if (difficulty == EnemyAI.Difficulty.Hard)
            return 1.15f;
        return 1f;
    }

    private Color EnemyColor(Wave wave)
    {
        float t = Mathf.InverseLerp(40f, 90f, wave.enemyHealth);
        return Color.Lerp(new Color(0.95f, 0.55f, 0.15f), new Color(0.85f, 0.15f, 0.12f), t);
    }

    private Vector3 GetSpawnPos()
    {
        if (spawnPoints != null && spawnPoints.Length > 0)
        {
            Transform spawn = spawnPoints[Random.Range(0, spawnPoints.Length)];
            if (spawn != null)
                return spawn.position;
        }

        return new Vector3(Random.Range(-18f, 18f), 1f, Random.Range(0f, 18f));
    }

    private int CountEnemies()
    {
        return Object.FindObjectsByType<EnemyHealth>(FindObjectsSortMode.None).Length;
    }

    private void ShowBanner(string text, float duration)
    {
        BannerText = text;
        BannerUntil = Time.time + duration;
    }
}
