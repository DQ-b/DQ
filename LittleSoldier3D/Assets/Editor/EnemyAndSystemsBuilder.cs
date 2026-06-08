using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public class EnemyAndSystemsBuilder
{
    [MenuItem("LittleSoldier/Build Enemies And Systems")]
    public static void Build()
    {
        GameObject player = GameObject.Find("Player");
        if (player == null)
        {
            Debug.LogError("Player was not found. Run LittleSoldier -> Build Training Scene first.");
            return;
        }

        if (player.GetComponent<PlayerHealth>() == null)
            player.AddComponent<PlayerHealth>();
        player.tag = "Player";

        GameObject gm = GameObject.Find("GameManager");
        if (gm == null)
            gm = new GameObject("GameManager");
        if (gm.GetComponent<GameManager>() == null)
            gm.AddComponent<GameManager>();
        if (gm.GetComponent<HUDManager>() == null)
            gm.AddComponent<HUDManager>();

        foreach (EnemyHealth old in Object.FindObjectsByType<EnemyHealth>(FindObjectsSortMode.None))
            Object.DestroyImmediate(old.gameObject);

        Material matEnemy = MakeMat(new Color(0.95f, 0.45f, 0.10f));

        Vector3[] spawns =
        {
            new Vector3(0, 1, 15),
            new Vector3(-10, 1, 12),
            new Vector3(10, 1, 12),
            new Vector3(-14, 1, 0),
            new Vector3(14, 1, 0)
        };

        foreach (Vector3 pos in spawns)
            CreateEnemy(pos, matEnemy);

        gm.GetComponent<GameManager>().killsToWin = spawns.Length;

        EditorSceneManager.MarkSceneDirty(EditorSceneManager.GetActiveScene());
        Debug.Log("Enemies, GameManager, and HUD generated. Press Play to test.");
    }

    private static void CreateEnemy(Vector3 pos, Material material)
    {
        GameObject enemy = GameObject.CreatePrimitive(PrimitiveType.Capsule);
        enemy.name = "Enemy";
        enemy.transform.position = pos;

        Object.DestroyImmediate(enemy.GetComponent<CapsuleCollider>());
        CharacterController controller = enemy.AddComponent<CharacterController>();
        controller.height = 2f;
        controller.radius = 0.5f;
        controller.center = Vector3.zero;

        Renderer renderer = enemy.GetComponent<Renderer>();
        if (renderer != null)
            renderer.sharedMaterial = material;

        enemy.AddComponent<EnemyHealth>();
        EnemyAI ai = enemy.AddComponent<EnemyAI>();
        ai.moveSpeed = 1.8f;
        ai.attackRange = 2.2f;
        ai.attackInterval = 1.4f;
        ai.attackDamage = 5f;
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
