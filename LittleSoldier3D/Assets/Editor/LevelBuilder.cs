using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public class LevelBuilder
{
    [MenuItem("LittleSoldier/Build Level (Map + Waves)")]
    public static void Build()
    {
        DestroyIfExists("MapExtras");
        DestroyIfExists("SpawnPoints");
        DestroyIfExists("WaveSystem");

        foreach (EnemyHealth enemy in Object.FindObjectsByType<EnemyHealth>(FindObjectsSortMode.None))
            Object.DestroyImmediate(enemy.gameObject);

        Material wallMaterial = MakeMat(new Color(0.50f, 0.50f, 0.56f));
        Material coverMaterial = MakeMat(new Color(0.42f, 0.47f, 0.30f));

        GameObject extras = new GameObject("MapExtras");
        AddCube(extras, "Inner_1", new Vector3(-8f, 2f, 6f), new Vector3(16f, 4f, 1f), wallMaterial);
        AddCube(extras, "Inner_2", new Vector3(8f, 2f, 6f), new Vector3(1f, 4f, 14f), wallMaterial);
        AddCube(extras, "Inner_3", new Vector3(-12f, 2f, 0f), new Vector3(1f, 4f, 18f), wallMaterial);
        AddCube(extras, "Inner_4", new Vector3(2f, 2f, 14f), new Vector3(20f, 4f, 1f), wallMaterial);
        AddCube(extras, "Inner_5", new Vector3(14f, 2f, -6f), new Vector3(16f, 4f, 1f), wallMaterial);

        Vector3[] covers =
        {
            new Vector3(-3f, 1f, -3f),
            new Vector3(5f, 1f, -8f),
            new Vector3(-15f, 1f, 8f),
            new Vector3(12f, 1f, 4f),
            new Vector3(0f, 1f, 10f),
            new Vector3(-6f, 1f, -10f),
            new Vector3(16f, 1f, -12f),
            new Vector3(-18f, 1f, -2f)
        };

        foreach (Vector3 cover in covers)
            AddCube(extras, "Cover", cover, new Vector3(2f, 2f, 2f), coverMaterial);

        GameObject spawnContainer = new GameObject("SpawnPoints");
        Vector3[] spawnPositions =
        {
            new Vector3(0f, 1f, 20f),
            new Vector3(-18f, 1f, 12f),
            new Vector3(18f, 1f, 12f),
            new Vector3(-18f, 1f, -8f),
            new Vector3(18f, 1f, -10f),
            new Vector3(0f, 1f, 8f),
            new Vector3(10f, 1f, 18f),
            new Vector3(-10f, 1f, 18f)
        };

        List<Transform> spawns = new List<Transform>();
        for (int i = 0; i < spawnPositions.Length; i++)
        {
            GameObject spawn = new GameObject("Spawn_" + (i + 1));
            spawn.transform.SetParent(spawnContainer.transform);
            spawn.transform.position = spawnPositions[i];
            spawns.Add(spawn.transform);
        }

        GameObject waveObject = new GameObject("WaveSystem");
        WaveManager waveManager = waveObject.AddComponent<WaveManager>();
        waveObject.AddComponent<WaveHUD>();
        waveManager.spawnPoints = spawns.ToArray();
        waveManager.startDelay = 1.5f;
        waveManager.interWaveDelay = 3f;
        waveManager.waves = new Wave[]
        {
            new Wave { enemyCount = 3, enemyHealth = 40f, enemyMoveSpeed = 3.0f, enemyAttackDamage = 6f },
            new Wave { enemyCount = 5, enemyHealth = 55f, enemyMoveSpeed = 3.5f, enemyAttackDamage = 8f },
            new Wave { enemyCount = 6, enemyHealth = 80f, enemyMoveSpeed = 4.0f, enemyAttackDamage = 11f },
        };

        EditorSceneManager.MarkSceneDirty(EditorSceneManager.GetActiveScene());
        Debug.Log("Level upgraded with map extras and wave system. 3 waves, 14 enemies total.");
    }

    private static void DestroyIfExists(string name)
    {
        GameObject gameObject = GameObject.Find(name);
        if (gameObject != null)
            Object.DestroyImmediate(gameObject);
    }

    private static void AddCube(GameObject parent, string name, Vector3 position, Vector3 scale, Material material)
    {
        GameObject gameObject = GameObject.CreatePrimitive(PrimitiveType.Cube);
        gameObject.name = name;
        gameObject.transform.SetParent(parent.transform);
        gameObject.transform.position = position;
        gameObject.transform.localScale = scale;

        Renderer renderer = gameObject.GetComponent<Renderer>();
        if (renderer != null)
            renderer.sharedMaterial = material;
    }

    private static Material MakeMat(Color color)
    {
        Shader shader = Shader.Find("Standard");
        if (shader == null)
            shader = Shader.Find("Universal Render Pipeline/Lit");

        Material material = new Material(shader);
        if (material.HasProperty("_Color"))
            material.SetColor("_Color", color);
        if (material.HasProperty("_BaseColor"))
            material.SetColor("_BaseColor", color);
        return material;
    }
}
