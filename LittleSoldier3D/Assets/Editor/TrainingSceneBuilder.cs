using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class TrainingSceneBuilder
{
    [MenuItem("LittleSoldier/Build Training Scene")]
    public static void Build()
    {
        Material matGround = MakeMat(new Color(0.30f, 0.30f, 0.30f));
        Material matWall = MakeMat(new Color(0.55f, 0.55f, 0.60f));
        Material matCover = MakeMat(new Color(0.45f, 0.50f, 0.30f));
        Material matTarget = MakeMat(new Color(0.85f, 0.20f, 0.20f));

        if (Camera.main != null)
            Object.DestroyImmediate(Camera.main.gameObject);

        GameObject ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
        ground.name = "Ground";
        ground.transform.localScale = new Vector3(5, 1, 5);
        SetMat(ground, matGround);

        CreateCube("Wall_N", new Vector3(0, 2, 25), new Vector3(50, 4, 1), matWall);
        CreateCube("Wall_S", new Vector3(0, 2, -25), new Vector3(50, 4, 1), matWall);
        CreateCube("Wall_E", new Vector3(25, 2, 0), new Vector3(1, 4, 50), matWall);
        CreateCube("Wall_W", new Vector3(-25, 2, 0), new Vector3(1, 4, 50), matWall);

        Vector3[] covers =
        {
            new Vector3(5, 1, 5),
            new Vector3(-6, 1, 8),
            new Vector3(0, 1, -7),
            new Vector3(8, 1, -4)
        };

        for (int i = 0; i < covers.Length; i++)
            CreateCube("Cover_" + (i + 1), covers[i], new Vector3(2, 2, 2), matCover);

        Vector3[] targets =
        {
            new Vector3(0, 1, 8),
            new Vector3(-8, 1, 3),
            new Vector3(9, 1, 6)
        };

        for (int i = 0; i < targets.Length; i++)
        {
            GameObject target = CreateCube("Target_" + (i + 1), targets[i], new Vector3(1, 2, 1), matTarget);
            target.AddComponent<Target>();
        }

        GameObject player = new GameObject("Player");
        player.transform.position = new Vector3(0, 1, -10);
        CharacterController characterController = player.AddComponent<CharacterController>();
        characterController.height = 2f;
        characterController.radius = 0.5f;
        characterController.center = Vector3.zero;
        player.AddComponent<PlayerMovement>();

        GameObject cameraObject = new GameObject("Main Camera");
        cameraObject.tag = "MainCamera";
        cameraObject.transform.SetParent(player.transform);
        cameraObject.transform.localPosition = new Vector3(0, 0.6f, 0);
        cameraObject.transform.localRotation = Quaternion.identity;
        Camera camera = cameraObject.AddComponent<Camera>();
        cameraObject.AddComponent<AudioListener>();

        MouseLook mouseLook = cameraObject.AddComponent<MouseLook>();
        mouseLook.playerBody = player.transform;

        GunRaycast gunRaycast = cameraObject.AddComponent<GunRaycast>();
        gunRaycast.fpsCam = camera;

        cameraObject.AddComponent<SimpleCrosshair>();

        GameObject spawn = new GameObject("PlayerSpawn");
        spawn.transform.position = new Vector3(0, 1, -10);

        EditorSceneManager.MarkSceneDirty(EditorSceneManager.GetActiveScene());
        Debug.Log("Training scene generated. Press Play to test.");
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

    private static void SetMat(GameObject gameObject, Material material)
    {
        Renderer renderer = gameObject.GetComponent<Renderer>();
        if (renderer != null)
            renderer.sharedMaterial = material;
    }

    private static GameObject CreateCube(string name, Vector3 position, Vector3 scale, Material material)
    {
        GameObject gameObject = GameObject.CreatePrimitive(PrimitiveType.Cube);
        gameObject.name = name;
        gameObject.transform.position = position;
        gameObject.transform.localScale = scale;
        SetMat(gameObject, material);
        return gameObject;
    }
}
