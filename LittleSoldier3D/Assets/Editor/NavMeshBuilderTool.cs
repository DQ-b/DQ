using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public class NavMeshBuilderTool
{
    [MenuItem("LittleSoldier/Bake NavMesh & Patrol")]
    public static void Build()
    {
        MarkNav("Ground");
        MarkNav("Wall_N");
        MarkNav("Wall_S");
        MarkNav("Wall_E");
        MarkNav("Wall_W");

        GameObject extras = GameObject.Find("MapExtras");
        if (extras != null)
        {
            foreach (Transform child in extras.transform)
                SetNav(child.gameObject);
        }

        UnityEditor.AI.NavMeshBuilder.ClearAllNavMeshes();
        UnityEditor.AI.NavMeshBuilder.BuildNavMesh();

        DestroyIfExists("PatrolPoints");
        GameObject patrolRoot = new GameObject("PatrolPoints");
        Vector3[] patrolPositions =
        {
            new Vector3(0f, 1f, 16f),
            new Vector3(13f, 1f, -2f),
            new Vector3(-13f, 1f, -6f),
            new Vector3(6f, 1f, 11f),
            new Vector3(-6f, 1f, 2f),
            new Vector3(15f, 1f, 9f),
            new Vector3(-16f, 1f, 4f),
            new Vector3(2f, 1f, -10f)
        };
        List<Transform> patrolPoints = MakePoints(patrolRoot, "Patrol_", patrolPositions);

        DestroyIfExists("CoverPoints");
        GameObject coverRoot = new GameObject("CoverPoints");
        Vector3[] coverPositions =
        {
            new Vector3(-3f, 1f, -1f),
            new Vector3(5f, 1f, -6f),
            new Vector3(-13f, 1f, 8f),
            new Vector3(10f, 1f, 5f),
            new Vector3(-6f, 1f, -8f),
            new Vector3(14f, 1f, -10f)
        };
        List<Transform> coverPoints = MakePoints(coverRoot, "Cover_", coverPositions);

        WaveManager waveManager = Object.FindFirstObjectByType<WaveManager>();
        if (waveManager == null)
        {
            Debug.LogError("WaveManager was not found. Run LittleSoldier -> Build Level (Map + Waves) first.");
            return;
        }

        waveManager.patrolPoints = patrolPoints.ToArray();
        waveManager.coverPoints = coverPoints.ToArray();
        waveManager.difficulty = EnemyAI.Difficulty.Normal;

        EditorSceneManager.MarkSceneDirty(EditorSceneManager.GetActiveScene());
        Debug.Log("NavMesh baked. Patrol and cover points are connected to WaveManager.");
    }

    private static List<Transform> MakePoints(GameObject root, string prefix, Vector3[] positions)
    {
        List<Transform> points = new List<Transform>();
        for (int i = 0; i < positions.Length; i++)
        {
            GameObject point = new GameObject(prefix + (i + 1));
            point.transform.SetParent(root.transform);
            point.transform.position = positions[i];
            points.Add(point.transform);
        }
        return points;
    }

    private static void MarkNav(string name)
    {
        GameObject gameObject = GameObject.Find(name);
        if (gameObject != null)
            SetNav(gameObject);
    }

    private static void SetNav(GameObject gameObject)
    {
        GameObjectUtility.SetStaticEditorFlags(gameObject, StaticEditorFlags.NavigationStatic);
    }

    private static void DestroyIfExists(string name)
    {
        GameObject gameObject = GameObject.Find(name);
        if (gameObject != null)
            Object.DestroyImmediate(gameObject);
    }
}
